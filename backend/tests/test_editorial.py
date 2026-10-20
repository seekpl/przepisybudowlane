"""Obieg redakcyjny: maszyna wykrywa, człowiek zatwierdza; autor nie zatwierdza własnej treści."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Editor
from app.models import EditorialEvent, Explanation, ExplanationVersion, LegalUnit
from app.modules.editorial.workflow import WorkflowError, public_version, transition

ANNA = Editor("anna", frozenset({"redaktor"}), "")
JAN = Editor("jan", frozenset({"recenzent"}), "")
OLA = Editor("ola", frozenset({"redaktor", "recenzent"}), "")


def draft(
    s: Session, slug: str = "warunki-techniczne-par-12-ust-1", author: str = "ola"
) -> ExplanationVersion:
    from app.modules.freshness.service import unit_text

    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == slug))
    expl = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
    no = max(v.version_no for v in expl.versions) + 1
    v = ExplanationVersion(
        explanation_id=expl.id,
        version_no=no,
        title="Nowe",
        body="Nowa treść objaśnienia.",
        author=author,
        based_on_unit_version_id=unit_text(s, unit).unit_version.id,
    )
    s.add(v)
    s.flush()
    return v


def test_author_cannot_approve_own_content_even_with_reviewer_role(seeded: Session) -> None:
    v = draft(seeded)
    transition(seeded, v, "recenzja", OLA)
    with pytest.raises(WorkflowError, match="Autor nie zatwierdza"):
        transition(seeded, v, "zatwierdzony", OLA)


def test_only_reviewer_role_approves(seeded: Session) -> None:
    v = draft(seeded, author="ola")
    transition(seeded, v, "recenzja", OLA)
    with pytest.raises(WorkflowError, match="recenzenta"):
        transition(seeded, v, "zatwierdzony", ANNA)


def test_only_author_sends_draft_to_review(seeded: Session) -> None:
    v = draft(seeded, author="ola")
    with pytest.raises(WorkflowError):
        transition(seeded, v, "recenzja", ANNA)


def test_cannot_publish_without_approval(seeded: Session) -> None:
    v = draft(seeded)
    transition(seeded, v, "recenzja", OLA)
    with pytest.raises(WorkflowError, match="Niedozwolone"):
        transition(seeded, v, "opublikowany", JAN)


def test_full_cycle_records_every_transition_and_new_version_becomes_public(seeded: Session) -> None:
    v = draft(seeded)
    transition(seeded, v, "recenzja", OLA)
    transition(seeded, v, "zatwierdzony", JAN, "Zgodne z § 12 ust. 1")
    assert v.reviewer == "jan" and v.verified_on is not None
    transition(seeded, v, "opublikowany", ANNA)
    events = seeded.scalars(
        select(EditorialEvent)
        .where(EditorialEvent.entity == "explanation_version", EditorialEvent.entity_id == v.id)
        .order_by(EditorialEvent.id)
    ).all()
    assert [(e.from_state, e.to_state, e.actor) for e in events] == [
        ("szkic", "recenzja", "ola"),
        ("recenzja", "zatwierdzony", "jan"),
        ("zatwierdzony", "opublikowany", "anna"),
    ]
    expl = seeded.get(Explanation, v.explanation_id)
    assert public_version(expl.versions).id == v.id
    # Poprzednia wersja zostaje w historii pod trwałym adresem.
    assert len([x for x in expl.versions if x.state == "opublikowany"]) == 2


def test_explanation_of_outdated_wording_cannot_be_published(seeded: Session) -> None:
    v = draft(seeded)
    v.based_on_unit_version_id = None
    transition(seeded, v, "recenzja", OLA)
    transition(seeded, v, "zatwierdzony", JAN)
    with pytest.raises(WorkflowError, match="inne brzmienie"):
        transition(seeded, v, "opublikowany", ANNA)


def test_suspension_needs_reason_and_restoring_needs_independent_reviewer(seeded: Session) -> None:
    unit = seeded.scalar(select(LegalUnit).where(LegalUnit.slug == "warunki-techniczne-par-12-ust-1"))
    v = public_version(seeded.scalar(select(Explanation).where(Explanation.unit_id == unit.id)).versions)
    with pytest.raises(WorkflowError):
        transition(seeded, v, "zawieszony", ANNA)
    transition(seeded, v, "zawieszony", ANNA, "Zgłoszenie ZB-1 do sprawdzenia")
    with pytest.raises(WorkflowError):
        transition(seeded, v, "opublikowany", Editor("demo-redaktor", frozenset({"recenzent"}), ""))  # autor
    transition(seeded, v, "opublikowany", JAN, "Sprawdzone ponownie")
    assert v.state == "opublikowany"


def test_public_card_shows_suspension_instead_of_outdated_explanation(
    seeded: Session, api: TestClient
) -> None:
    unit = seeded.scalar(select(LegalUnit).where(LegalUnit.slug == "warunki-techniczne-par-12-ust-1"))
    v = public_version(seeded.scalar(select(Explanation).where(Explanation.unit_id == unit.id)).versions)
    transition(seeded, v, "zawieszony", ANNA, "Przepis się zmienił")
    seeded.commit()
    card = api.get("/api/v1/przepisy/warunki-techniczne-par-12-ust-1").json()
    assert card["explanation_status"] == "zawieszone"
    assert card["explanation"]["suspended_reason"] == "Przepis się zmienił"


def test_editorial_api_requires_token_and_enforces_roles(seeded: Session, api: TestClient) -> None:
    assert api.get("/api/v1/redakcja/zadania").status_code == 401
    assert api.get("/api/v1/redakcja/zadania", headers={"Authorization": "Bearer zly"}).status_code == 401
    me = api.get("/api/v1/redakcja/ja", headers={"Authorization": "Bearer tok-anna"}).json()
    assert me == {"name": "anna", "roles": ["redaktor"]}

    created = api.post(
        "/api/v1/redakcja/objasnienia",
        headers={"Authorization": "Bearer tok-anna"},
        json={"unit_slug": "warunki-techniczne-par-12-ust-1", "body": "Nowe objaśnienie do sprawdzenia."},
    )
    assert created.status_code == 201
    vid = created.json()["id"]
    url = f"/api/v1/redakcja/tresci/explanation_version/{vid}/przejscie"
    assert (
        api.post(url, headers={"Authorization": "Bearer tok-anna"}, json={"to_state": "recenzja"}).status_code
        == 200
    )
    self_approve = api.post(
        url, headers={"Authorization": "Bearer tok-anna"}, json={"to_state": "zatwierdzony"}
    )
    assert self_approve.status_code == 409
    assert (
        api.post(
            url, headers={"Authorization": "Bearer tok-jan"}, json={"to_state": "zatwierdzony"}
        ).status_code
        == 200
    )
    assert (
        api.post(
            url, headers={"Authorization": "Bearer tok-jan"}, json={"to_state": "opublikowany"}
        ).status_code
        == 200
    )
    card = api.get("/api/v1/przepisy/warunki-techniczne-par-12-ust-1").json()
    assert card["explanation"]["version_id"] == vid
    assert card["explanation"]["is_demo"] is False
    history = api.get(
        f"/api/v1/redakcja/tresci/explanation_version/{vid}/historia",
        headers={"Authorization": "Bearer tok-jan"},
    ).json()
    assert [h["to_state"] for h in history] == ["szkic", "recenzja", "zatwierdzony", "opublikowany"]
