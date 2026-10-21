"""Synchronizacja z ELI na zapisanych (syntetycznych) odpowiedziach: idempotencja, wykrywanie zmian, awarie."""

from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ContentFlag,
    DetectedAmendment,
    EditorialTask,
    Explanation,
    ExplanationVersion,
    LegalTextVersion,
    LegalUnit,
    LegalUnitVersion,
    SourceFetch,
    SourceSnapshot,
    SyncCheckpoint,
    SyncRun,
)
from app.modules.archive.storage import Archive, sha256
from app.modules.freshness import service as fresh
from app.modules.search.service import rebuild_index
from tests.conftest import FIXTURES, NOW, FakeEli, only_act

PB_TEXT = "/eli/acts/DU/2026/524/text.html"


def count(s: Session, model: type) -> int:
    return s.scalar(select(func.count()).select_from(model)) or 0


def test_first_sync_builds_consolidated_text_units_and_amendments(  # type: ignore[no-untyped-def]
    seeded: Session, make_sync, archive_dir, fake_eli: FakeEli
) -> None:
    only_act(seeded, "prawo-budowlane")
    report = make_sync().run()
    assert report.status == "sukces", report.errors

    s = seeded
    s.expire_all()
    tv = fresh.current_text(s, 1)
    assert tv is not None
    assert (tv.text_type, tv.source_eli, tv.journal_display) == (
        "jednolity",
        "DU/2026/524",
        "Dz.U. 2026 poz. 524",
    )
    assert tv.legal_status_date.isoformat() == "2026-03-20"
    assert tv.review_state == "zaakceptowany" and tv.parse_quality == 1.0

    # Surowa odpowiedź zachowana z sumą SHA-256 i dostępna w archiwum.
    snap = s.scalar(select(SourceSnapshot).where(SourceSnapshot.url.endswith(PB_TEXT)))
    assert snap is not None
    assert snap.sha256 == sha256((FIXTURES / "DU_2026_524.html").read_bytes())
    assert Archive(archive_dir).get(snap.storage_key) == (FIXTURES / "DU_2026_524.html").read_bytes()

    # Nowelizacje sprzed roku przed stanem prawnym pomijamy bez pobierania; z okna — zapisujemy.
    # Ta z 2025 r. jest w tekście jednolitym (nie „późniejsza”), ta z września 2026 r. — jest późniejsza.
    elis = set(s.scalars(select(DetectedAmendment.amending_eli)))
    assert elis == {"DU/2025/100", "DU/2026/900"}
    assert "/eli/acts/DU/2019/50" not in fake_eli.calls
    tasks = s.scalars(select(EditorialTask.dedupe_key)).all()
    assert "nowelizacja:1:DU/2026/900" in tasks
    assert "nowelizacja:1:DU/2025/100" not in tasks
    assert s.get(SyncCheckpoint, "eli") is not None


def test_unit_status_after_sync_shows_upcoming_amendment(seeded: Session, make_sync) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    make_sync().run()
    from app.models import LegalUnit

    unit = seeded.scalar(select(LegalUnit).where(LegalUnit.slug == "prawo-budowlane-art-29-ust-1-pkt-1a"))
    f = fresh.for_unit(seeded, unit)
    assert f.status == "zmiana"
    assert f.effective_date.isoformat() == "2027-01-01"


def test_rerun_is_idempotent(seeded: Session, make_sync) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    make_sync().run()
    models = (LegalTextVersion, LegalUnitVersion, DetectedAmendment, EditorialTask)

    def snapshots() -> int:
        # Lista zmian ma w adresie parametr „since”, więc każde jej pobranie to osobny, nowy dokument.
        return (
            seeded.scalar(
                select(func.count()).select_from(SourceSnapshot).where(SourceSnapshot.kind != "changes")
            )
            or 0
        )

    before = {m: count(seeded, m) for m in models} | {"snapshots": snapshots()}
    fetches = count(seeded, SourceFetch)
    report = make_sync().run()
    assert report.status == "sukces"
    after = {m: count(seeded, m) for m in models} | {"snapshots": snapshots()}
    assert after == before
    assert count(seeded, SyncRun) == 2
    # Każde pobranie jest odnotowane — z nich liczymy wiek danych.
    assert count(seeded, SourceFetch) > fetches


def test_changed_unit_suspends_published_explanation_and_flags_wizard_branch(  # type: ignore[no-untyped-def]
    seeded: Session, make_sync, fake_eli: FakeEli, set_now
) -> None:
    from app.models import Explanation, LegalUnit
    from app.modules.content.seed import DEMO_AUTHOR, DEMO_REVIEWER
    from app.modules.editorial.workflow import transition

    only_act(seeded, "prawo-budowlane")
    make_sync().run()
    s = seeded
    s.expire_all()

    # Redakcja publikuje objaśnienie do brzmienia z ELI (nowa wersja objaśnienia, stara zostaje w historii).
    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == "prawo-budowlane-art-29-ust-1-pkt-1a"))
    current = fresh.unit_text(s, unit).unit_version
    expl = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
    v2 = ExplanationVersion(
        explanation_id=expl.id,
        version_no=2,
        title="Co to znaczy",
        body="Treść.",
        author=DEMO_AUTHOR.name,
        based_on_unit_version_id=current.id,
    )
    s.add(v2)
    s.flush()
    for state, who in (
        ("recenzja", DEMO_AUTHOR),
        ("zatwierdzony", DEMO_REVIEWER),
        ("opublikowany", DEMO_REVIEWER),
    ):
        transition(s, v2, state, who)
    s.commit()

    # W ELI pojawia się nowe brzmienie pkt 1a; lista zmian je zgłasza.
    html = (
        (FIXTURES / "DU_2026_524.html")
        .read_text(encoding="utf-8")
        .replace("do 70 m<sup>2</sup>", "do 90 m<sup>2</sup>")
    )
    fake_eli.routes[PB_TEXT] = (200, html.encode(), "text/html")
    fake_eli.set_json("/eli/changes/acts", [{"ELI": "DU/2026/524", "changeDate": "2026-10-20T10:30:00"}])
    set_now(NOW + timedelta(hours=1))
    report = make_sync().run()
    assert report.status == "sukces"
    assert report.outcomes[0].new_text_version and report.outcomes[0].changed_units >= 1

    s.expire_all()
    assert s.get(ExplanationVersion, v2.id).state == "zawieszony"
    assert s.scalar(
        select(EditorialTask).where(EditorialTask.kind == "zmiana_tekstu", EditorialTask.unit_id == unit.id)
    )
    # Gałęzie kreatora oparte na pkt 1a są zawieszone do przeglądu; pkt 1 (bez zmian) — nie.
    flagged = s.scalars(select(ContentFlag.entity_id)).all()
    from app.models import DecisionTreeNodeVersion

    keys = {s.get(DecisionTreeNodeVersion, i).node_key for i in flagged}
    assert "wynik-zgloszenie-70" in keys
    assert "wynik-zgloszenie" not in keys
    # Historia nie jest nadpisywana: stare brzmienie nadal ma swoją wersję.
    assert count(s, LegalTextVersion) == 4  # dwa teksty z seeda (PB, WT) + dwa brzmienia z ELI


def test_eli_outage_keeps_old_data_does_not_move_checkpoint_and_ages_into_warning(  # type: ignore[no-untyped-def]
    seeded: Session, make_sync, fake_eli: FakeEli, set_now
) -> None:
    from app.models import LegalUnit

    only_act(seeded, "prawo-budowlane")
    make_sync().run()
    checkpoint = seeded.get(SyncCheckpoint, "eli").last_success_at

    fake_eli.routes["/eli/acts/DU/1994/414"] = (503, b"Service Unavailable", "text/plain")
    set_now(NOW + timedelta(days=4))
    report = make_sync().run()
    assert report.status == "blad"
    assert "metadata" in report.errors[0]["blad"]

    s = seeded
    s.expire_all()
    assert s.get(SyncCheckpoint, "eli").last_success_at == checkpoint
    assert s.scalar(select(EditorialTask).where(EditorialTask.kind == "awaria_synchronizacji"))
    failed = s.scalars(select(SourceFetch).where(SourceFetch.ok.is_(False))).all()
    assert failed and failed[0].http_status == 503
    # Stare dane zostają, ale po progu karta mówi wprost, że nie potwierdziliśmy aktualności.
    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == "prawo-budowlane-art-28-ust-1"))
    assert fresh.unit_text(s, unit).unit_version is not None
    f = fresh.for_unit(s, unit)
    assert f.status == "niepotwierdzona"
    assert "dane_nieswieze" in [r.code for r in f.reasons]


def test_invalid_metadata_pauses_sync_as_contract_violation(
    seeded: Session, make_sync, fake_eli: FakeEli
) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    fake_eli.set_json("/eli/acts/DU/1994/414", {"ELI": "DU/1994/414", "publisher": "DU"})
    report = make_sync().run()
    assert report.status == "wstrzymany"
    assert report.alarm
    assert "schematem" in report.errors[0]["blad"]


def test_broken_json_pauses_sync(seeded: Session, make_sync, fake_eli: FakeEli) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    fake_eli.routes["/eli/acts/DU/1994/414"] = (200, b"{not json", "application/json")
    report = make_sync().run()
    assert report.status == "wstrzymany"
    assert report.contract_violations == []


def test_pdf_only_text_goes_to_human_review_not_publication(
    seeded: Session, make_sync, fake_eli: FakeEli
) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    meta = json.loads((FIXTURES / "DU_2026_524.json").read_text())
    meta["textHTML"] = False
    fake_eli.set_json("/eli/acts/DU/2026/524", meta)
    fake_eli.routes["/eli/acts/DU/2026/524/text.pdf"] = (200, b"%PDF-1.7 test", "application/pdf")
    assert make_sync().run().status == "sukces"
    s = seeded
    s.expire_all()
    tv = s.scalar(select(LegalTextVersion).where(LegalTextVersion.origin == "eli"))
    assert tv.review_state == "do_kontroli"
    assert s.scalar(select(EditorialTask).where(EditorialTask.kind == "kontrola_parsera"))
    # Publicznie nadal widać tekst z seeda, nie niesprawdzony PDF.
    assert fresh.current_text(s, tv.act_id).origin == "redakcja"


def test_low_quality_parse_goes_to_review(seeded: Session, make_sync, fake_eli: FakeEli) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    fake_eli.routes[PB_TEXT] = (
        200,
        "<p>Art. 5. Tekst.</p><p>Art. 3. Cofnięta numeracja.</p>".encode(),
        "text/html",
    )
    make_sync().run()
    seeded.expire_all()
    tv = seeded.scalar(select(LegalTextVersion).where(LegalTextVersion.origin == "eli"))
    assert tv.review_state == "do_kontroli"
    assert tv.parse_quality < 0.98


def test_changes_feed_failure_falls_back_to_full_refresh(
    seeded: Session, make_sync, fake_eli: FakeEli, set_now
) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    make_sync().run()
    fake_eli.routes["/eli/changes/acts"] = (500, b"", "text/plain")
    set_now(NOW + timedelta(hours=2))
    report = make_sync().run()
    assert report.status == "czesciowy"
    assert report.outcomes[0].ok


def test_search_index_contains_synced_articles(seeded: Session, make_sync) -> None:  # type: ignore[no-untyped-def]
    only_act(seeded, "prawo-budowlane")
    make_sync().run()
    seeded.expire_all()
    rebuild_index(seeded)
    seeded.commit()
    from app.modules.search.service import search

    hits = search(seeded, "strony postępowania obszar oddziaływania").hits
    assert any(h.ref == "prawo-budowlane-art-28" for h in hits)


def test_accepting_reviewed_text_replaces_previous_and_suspends_changed_explanations(  # type: ignore[no-untyped-def]
    seeded: Session, make_sync, fake_eli: FakeEli, api
) -> None:
    only_act(seeded, "prawo-budowlane")
    html = (FIXTURES / "DU_2026_524.html").read_text(encoding="utf-8")
    html = html.replace("z zastrzeżeniem art. 29–31.", "z zastrzeżeniem art. 29–31a.")
    # Cofnięta numeracja obniża jakość — tekst idzie do kontroli zamiast prosto na kartę.
    fake_eli.routes[PB_TEXT] = (200, (html + "<p>Art. 3. Cofnięta numeracja.</p>").encode(), "text/html")
    make_sync().run()
    seeded.expire_all()
    tv = seeded.scalar(select(LegalTextVersion).where(LegalTextVersion.origin == "eli"))
    assert tv.review_state == "do_kontroli"
    assert fresh.current_text(seeded, tv.act_id).origin == "redakcja"

    res = api.post(
        f"/api/v1/redakcja/teksty/{tv.id}/decyzja",
        headers={"Authorization": "Bearer tok-jan"},
        json={"accept": True, "comment": "Porównane z oryginałem w Dz.U."},
    )
    assert res.status_code == 200, res.text
    assert res.json()["zmienione_jednostki"] >= 1
    seeded.expire_all()
    assert fresh.current_text(seeded, tv.act_id).id == tv.id
    unit = seeded.scalar(select(LegalUnit).where(LegalUnit.slug == "prawo-budowlane-art-28-ust-1"))
    explanation = seeded.scalar(
        select(ExplanationVersion)
        .join(Explanation, Explanation.id == ExplanationVersion.explanation_id)
        .where(Explanation.unit_id == unit.id)
    )
    assert explanation.state == "zawieszony"
    assert seeded.scalar(
        select(EditorialTask).where(EditorialTask.kind == "zmiana_tekstu", EditorialTask.unit_id == unit.id)
    )
