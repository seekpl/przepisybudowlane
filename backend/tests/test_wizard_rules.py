"""Reguły kreatora z art. 29 Prawa budowlanego (arkusz, działanie 4.1): automat proponuje, recenzent decyduje."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LegalTextVersion, WizardRule
from app.modules.content.wizard_rules import describe, extract
from tests.conftest import FIXTURES, FakeEli, only_act

JAN = {"Authorization": "Bearer tok-jan"}  # recenzent
ANNA = {"Authorization": "Bearer tok-anna"}  # redaktor
PB_PDF = FIXTURES / "recorded" / "acts" / "DU" / "2026" / "524" / "text.pdf"


@pytest.fixture(scope="module")
def real_rules():  # type: ignore[no-untyped-def]
    if not PB_PDF.exists():
        pytest.skip("brak nagrania t.j. Prawa budowlanego")
    from app.modules.parser.pdf import parse_pdf

    units = {k: u.content for k, u in parse_pdf(Path(PB_PDF).read_bytes()).units.items()}
    return {r.unit_key: r for r in extract(units)}


def test_rules_from_real_article_29(real_rules) -> None:  # type: ignore[no-untyped-def]
    garage = real_rules["art_29.ust_1.pkt_14.lit_b"]
    assert garage.requirement == "zgloszenie" and garage.object_text == "wolno stojących garaży"
    # Część wspólna po literach („– o powierzchni zabudowy do 35 m², przy czym …”) dotyczy też garaży.
    assert [describe(c) for c in garage.conditions] == [
        "powierzchnia zabudowy nie więcej niż 35 m²",
        "najwyżej 2 takie obiekty na każde 500 m² działki",
    ]
    assert [describe(c) for c in real_rules["art_29.ust_1.pkt_21"].conditions] == [
        "wysokość więcej niż 2,20 m"
    ]
    fence = real_rules["art_29.ust_2.pkt_20"]
    assert fence.requirement == "bez_zgloszenia"
    assert [describe(c) for c in fence.conditions] == ["wysokość nie więcej niż 2,20 m"]
    cabin = [describe(c) for c in real_rules["art_29.ust_1.pkt_16.lit_b"].conditions]
    assert (
        "powierzchnia zabudowy więcej niż 35 m²" in cabin
        and "powierzchnia zabudowy nie więcej niż 70 m²" in cabin
    )


def test_accepted_text_yields_proposals_reviewed_by_human(seeded: Session, api: TestClient) -> None:
    proposals = api.get("/api/v1/redakcja/reguly-kreatora", headers=JAN).json()
    assert proposals and all(p["stan"] == "propozycja" for p in proposals)
    pkt_1a = next(p for p in proposals if p["jednostka"] == "art. 29 ust. 1 pkt 1a")
    assert "powierzchnia zabudowy nie więcej niż 70 m²" in pkt_1a["warunki"]
    url = f"/api/v1/redakcja/reguly-kreatora/{pkt_1a['id']}/decyzja"
    assert api.post(url, headers=ANNA, json={"accept": True}).status_code == 403
    assert (
        api.post(url, headers=JAN, json={"accept": True, "comment": "Zgodne z brzmieniem"}).json()["stan"]
        == "zatwierdzona"
    )
    assert api.post(url, headers=JAN, json={"accept": True}).status_code == 409


def test_unchanged_point_keeps_decision_changed_point_returns_to_queue(  # type: ignore[no-untyped-def]
    seeded: Session, api: TestClient, make_sync, fake_eli: FakeEli
) -> None:
    rules = seeded.scalars(select(WizardRule)).all()
    for r in rules:
        r.state, r.reviewed_by = "zatwierdzona", "jan"
    seeded.commit()
    only_act(seeded, "prawo-budowlane")
    html = (
        (FIXTURES / "DU_2026_524.html")
        .read_text(encoding="utf-8")
        .replace("do 70 m<sup>2</sup>", "do 90 m<sup>2</sup>")
    )
    fake_eli.routes["/eli/acts/DU/2026/524/text.html"] = (200, html.encode(), "text/html")
    fake_eli.set_json("/eli/changes/acts", [{"ELI": "DU/2026/524", "changeDate": "2026-10-20T09:00:00"}])
    make_sync().run()
    seeded.expire_all()
    newest = seeded.scalar(select(LegalTextVersion).order_by(LegalTextVersion.id.desc()))
    states = {
        r.unit_key: r.state
        for r in seeded.scalars(select(WizardRule).where(WizardRule.text_version_id == newest.id))
    }
    assert states["art_29.ust_1.pkt_1a"] == "propozycja"  # nowe brzmienie — znowu do przeglądu
    assert states["art_29.ust_1.pkt_1"] == "zatwierdzona"  # bez zmian — decyzja zostaje
