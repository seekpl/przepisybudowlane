"""Kontrakt z ELI API, nagrywanie i odtwarzanie odpowiedzi, alarm wstrzymujący synchronizację.

Część testów działa na nagraniach z prawdziwego API (``fixtures/eli/recorded``, zapisuje je workflow
``eli-nagrania``). Gdy nagrań jeszcze nie ma, te testy są pomijane — reszta działa na danych syntetycznych.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_sessionmaker
from app.models import LegalTextVersion, LegalUnit, LegalUnitVersion, SourceAlarm, SyncRun
from app.modules.archive.storage import Archive
from app.modules.eli.client import EliClient
from app.modules.eli.contract import KNOWN_REFERENCE_KEYS, check_metadata
from app.modules.eli.recording import INDEX, RecordingTransport, ReplayTransport, relative_file
from app.modules.eli.schemas import REFERENCE_ROLES
from app.modules.freshness import service as fresh
from app.modules.parser.units import parse_units
from app.modules.sync.service import SyncService
from tests.conftest import FIXTURES, FakeEli, only_act

RECORDED = FIXTURES / "recorded"
RECORDED_INDEX = RECORDED / INDEX
needs_recording = pytest.mark.skipif(
    not RECORDED_INDEX.exists(), reason="brak nagrań z ELI (workflow eli-nagrania jeszcze ich nie zapisał)"
)
JAN = {"Authorization": "Bearer tok-jan"}


def _service(transport: httpx.BaseTransport, archive_dir: Path, base: str = "https://api.example.test/eli"):  # type: ignore[no-untyped-def]
    client = EliClient(base, transport=transport, max_retries=1, backoff=0, sleep=lambda _: None)
    return SyncService(get_sessionmaker(), client, Archive(archive_dir), get_settings())


def _unit(s: Session, slug: str = "prawo-budowlane-art-28-ust-1") -> LegalUnit:
    unit = s.scalar(select(LegalUnit).where(LegalUnit.slug == slug))
    assert unit is not None
    return unit


# --- kontrakt jednej odpowiedzi -------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("DU_*.json")))
def test_synthetic_fixtures_satisfy_contract(name: str) -> None:
    raw = (FIXTURES / name).read_bytes()
    is_tj = "Tekst jednolity dla aktu" in (json.loads(raw).get("references") or {})
    assert check_metadata(raw, consolidated_text=is_tj) == []


def test_unknown_reference_key_is_a_violation() -> None:
    meta = json.loads((FIXTURES / "DU_1994_414.json").read_text())
    meta["references"]["Akty nowego rodzaju"] = []
    codes = [v.code for v in check_metadata(meta)]
    assert codes == ["nieznany_klucz_powiazania"]


def test_consolidated_text_without_legal_status_date_is_a_violation() -> None:
    meta = json.loads((FIXTURES / "DU_2026_524.json").read_text())
    meta.pop("legalStatusDate")
    meta["inForce"] = "IN_FORCE"
    assert [v.code for v in check_metadata(meta, consolidated_text=True)] == ["brak_stanu_prawnego"]
    # Ten sam brak w akcie bazowym nie jest naruszeniem: stan prawny deklaruje tekst jednolity.
    assert check_metadata(meta) == []
    # Ani w t.j. aktu uchylonego — tak wygląda prawdziwe DU/2022/1225 (nagranie z 21.10.2026).
    meta["inForce"] = "NOT_IN_FORCE"
    assert check_metadata(meta, consolidated_text=True) == []


def test_schema_change_and_broken_json_are_violations() -> None:
    assert [v.code for v in check_metadata({"ELI": "DU/1994/414"})] == ["schemat"]
    assert [v.code for v in check_metadata(b"<html>")] == ["json"]
    assert [v.code for v in check_metadata(b"[]")] == ["json"]


def test_reference_roles_are_part_of_closed_dictionary() -> None:
    for keys in REFERENCE_ROLES.values():
        assert set(keys) <= KNOWN_REFERENCE_KEYS


# --- nagrywanie i odtwarzanie -----------------------------------------------------------------------


def test_relative_file_maps_eli_paths_and_rejects_others() -> None:
    assert relative_file("/eli", "/eli/acts/DU/1994/414") == "acts/DU/1994/414.json"
    assert relative_file("/eli/", "/eli/acts/DU/2026/524/text.html") == "acts/DU/2026/524/text.html"
    assert relative_file("/eli", "/inne/acts/DU/1994/414") is None
    assert relative_file("/eli", "/eli/acts/../../etc/passwd") is None
    assert relative_file("/eli", "/eli") is None


def test_recorded_responses_replay_to_identical_sync(  # type: ignore[no-untyped-def]
    manifest: Session, fake_eli: FakeEli, tmp_path: Path
) -> None:
    seeded = manifest
    only_act(seeded, "prawo-budowlane")
    out = tmp_path / "recorded"
    recorder = RecordingTransport(httpx.MockTransport(fake_eli.handler), out, "/eli")
    assert _service(recorder, tmp_path / "a1").run().status == "sukces"
    recorder.save()

    index = json.loads((out / INDEX).read_text())
    assert (out / "acts/DU/1994/414.json").read_bytes() == (FIXTURES / "DU_1994_414.json").read_bytes()
    assert (out / "acts/DU/2026/524/text.html").read_bytes() == (FIXTURES / "DU_2026_524.html").read_bytes()
    assert index["acts/DU/2026/524/text.html"]["status"] == 200
    assert not any(k.startswith("changes") for k in index), "lista zmian zależy od chwili — nie nagrywamy"

    seeded.expire_all()
    versions = seeded.scalars(select(LegalTextVersion.id).where(LegalTextVersion.origin == "eli")).all()
    replay = _service(ReplayTransport(out, "/eli"), tmp_path / "a2")
    assert replay.run("odtworzenie").status == "sukces"
    seeded.expire_all()
    # Te same bajty → te same migawki i ta sama wersja tekstu (idempotencja), żadnych nowych zadań.
    assert (
        seeded.scalars(select(LegalTextVersion.id).where(LegalTextVersion.origin == "eli")).all() == versions
    )


def test_rerecording_unchanged_source_gives_no_diff_and_prunes_stale_files(
    fake_eli: FakeEli, tmp_path: Path
) -> None:
    out = tmp_path / "recorded"
    first = RecordingTransport(httpx.MockTransport(fake_eli.handler), out, "/eli")
    with httpx.Client(transport=first, base_url="https://x.test/eli") as http:
        http.get("/acts/DU/1994/414")
        http.get("/acts/DU/2026/524")
    first.save(prune=True)
    snapshot = (out / INDEX).read_text()

    second = RecordingTransport(httpx.MockTransport(fake_eli.handler), out, "/eli")
    with httpx.Client(transport=second, base_url="https://x.test/eli") as http:
        http.get("/acts/DU/1994/414")
    second.save()  # bez przycinania: nic nie znika
    assert (out / INDEX).read_text() == snapshot

    third = RecordingTransport(httpx.MockTransport(fake_eli.handler), out, "/eli")
    with httpx.Client(transport=third, base_url="https://x.test/eli") as http:
        http.get("/acts/DU/1994/414")
    third.save(prune=True)
    index = json.loads((out / INDEX).read_text())
    assert list(index) == ["acts/DU/1994/414.json"]
    assert index["acts/DU/1994/414.json"] == json.loads(snapshot)["acts/DU/1994/414.json"]
    assert not (out / "acts/DU/2026/524.json").exists()


def test_failed_or_transient_responses_do_not_overwrite_recording(fake_eli: FakeEli, tmp_path: Path) -> None:
    out = tmp_path / "recorded"
    first = RecordingTransport(httpx.MockTransport(fake_eli.handler), out, "/eli")
    with httpx.Client(transport=first, base_url="https://x.test/eli") as http:
        http.get("/acts/DU/1994/414")
    first.save(prune=True)
    snapshot = (out / INDEX).read_text()

    fake_eli.set_json("/eli/acts/DU/1994/414", {"error": "przeciążenie"}, status=503)
    flaky = RecordingTransport(httpx.MockTransport(fake_eli.handler), out, "/eli")
    with httpx.Client(transport=flaky, base_url="https://x.test/eli") as http:
        assert http.get("/acts/DU/1994/414").status_code == 503
    assert flaky.pending == {}
    flaky.save()
    assert (out / INDEX).read_text() == snapshot
    assert (out / "acts/DU/1994/414.json").exists()


def test_replay_answers_404_for_unrecorded_resources(tmp_path: Path) -> None:
    client = httpx.Client(transport=ReplayTransport(tmp_path, "/eli"), base_url="https://x.test/eli")
    assert client.get("/acts/DU/2000/1").status_code == 404
    assert client.get("/changes/acts", params={"since": "2026-10-01T00:00:00"}).json() == []


# --- alarm i wstrzymanie (działania 1.3 i 1.5) --------------------------------------------------------


def test_contract_violation_pauses_sync_and_downgrades_every_card(  # type: ignore[no-untyped-def]
    seeded: Session, make_sync, fake_eli: FakeEli, api: TestClient
) -> None:
    only_act(seeded, "prawo-budowlane")
    assert make_sync().run().status == "sukces"
    seeded.expire_all()
    before = fresh.for_unit(seeded, _unit(seeded)).status
    assert before != "niepotwierdzona"  # w danych syntetycznych: „zmiana w drodze”

    meta = json.loads((FIXTURES / "DU_1994_414.json").read_text())
    meta["references"]["Akty nowego rodzaju"] = [{"id": "DU/2026/1", "date": "2026-10-01"}]
    fake_eli.set_json("/eli/acts/DU/1994/414", meta)
    report = make_sync().run()
    assert report.status == "wstrzymany"
    assert report.alarm

    seeded.expire_all()
    alarm = seeded.scalar(select(SourceAlarm).where(SourceAlarm.resolved_at.is_(None)))
    assert alarm is not None and alarm.kind == "kontrakt"
    assert alarm.details["naruszenia"][0]["kod"] == "nieznany_klucz_powiazania"
    f = fresh.for_unit(seeded, _unit(seeded))
    assert f.status == "niepotwierdzona"
    assert f.notices[0].code == "synchronizacja_wstrzymana"
    stan = api.get("/api/v1/stan").json()
    assert stan["alarm"]["title"] == alarm.title

    # Dopóki alarm jest otwarty, kolejne przebiegi niczego nie pobierają.
    fake_eli.calls.clear()
    assert make_sync().run().status == "wstrzymany"
    assert fake_eli.calls == []

    # Człowiek sprawdza zmianę (tu: źródło wróciło do znanego formatu) i zamyka alarm.
    fake_eli.routes["/eli/acts/DU/1994/414"] = (
        200,
        (FIXTURES / "DU_1994_414.json").read_bytes(),
        "application/json",
    )
    assert (
        api.post(f"/api/v1/redakcja/alarmy/{alarm.id}/zamknij", json={"resolution": "x"}).status_code == 401
    )
    closed = api.post(
        f"/api/v1/redakcja/alarmy/{alarm.id}/zamknij",
        headers=JAN,
        json={"resolution": "Sprawdzone: chwilowa zmiana po stronie ELI, format wrócił."},
    )
    assert closed.status_code == 200 and closed.json()["resolved_by"] == "jan"
    again = api.post(
        f"/api/v1/redakcja/alarmy/{alarm.id}/zamknij", headers=JAN, json={"resolution": "Ponowna próba"}
    )
    assert again.status_code == 409
    assert make_sync().run().status == "sukces"
    seeded.expire_all()
    assert fresh.for_unit(seeded, _unit(seeded)).status == before
    assert api.get("/api/v1/stan").json()["alarm"] is None


def test_recording_collects_violations_instead_of_stopping(  # type: ignore[no-untyped-def]
    seeded: Session, fake_eli: FakeEli, archive_dir: Path
) -> None:
    only_act(seeded, "prawo-budowlane")
    meta = json.loads((FIXTURES / "DU_2026_524.json").read_text())
    meta.pop("legalStatusDate")
    meta["inForce"] = "IN_FORCE"
    fake_eli.set_json("/eli/acts/DU/2026/524", meta)
    client = EliClient(
        "https://api.example.test/eli",
        transport=httpx.MockTransport(fake_eli.handler),
        max_retries=1,
        backoff=0,
        sleep=lambda _: None,
    )
    service = SyncService(
        get_sessionmaker(), client, Archive(archive_dir), get_settings(), enforce_contract=False
    )
    report = service.run("nagranie")
    assert report.status != "wstrzymany"
    assert [v["kod"] for v in report.contract_violations] == ["brak_stanu_prawnego"]
    assert seeded.scalar(select(SourceAlarm)) is None


# --- nagrania z prawdziwego ELI (działania 1.2, 1.5, 1.6) ------------------------------------------


def _recorded_metadata() -> list[Path]:
    if not RECORDED_INDEX.exists():
        return []
    return sorted(p for p in (RECORDED / "acts").rglob("*.json"))


@needs_recording
@pytest.mark.parametrize("path", _recorded_metadata(), ids=lambda p: str(p.relative_to(RECORDED)))
def test_recorded_metadata_satisfies_contract(path: Path) -> None:
    raw = path.read_bytes()
    data = json.loads(raw)
    is_tj = any(k in (data.get("references") or {}) for k in REFERENCE_ROLES["consolidates"])
    assert check_metadata(raw, consolidated_text=is_tj) == []


@needs_recording
def test_recorded_index_matches_files() -> None:
    import hashlib

    index = json.loads(RECORDED_INDEX.read_text())
    assert index, "puste nagranie"
    for rel, meta in index.items():
        if meta["status"] == 200:
            assert hashlib.sha256((RECORDED / rel).read_bytes()).hexdigest() == meta["sha256"], rel


@needs_recording
def test_replay_of_recorded_eli_routes_low_quality_texts_to_review(  # type: ignore[no-untyped-def]
    seeded: Session, tmp_path: Path
) -> None:
    """Pełna synchronizacja na nagraniach: kontrakt egzekwowany, parser z progiem jakości, PDF do kontroli."""
    report = _service(ReplayTransport(RECORDED, "/eli"), tmp_path / "archive").run("odtworzenie")
    assert report.status == "sukces", report.errors
    threshold = get_settings().parser_quality_threshold
    seeded.expire_all()
    texts = seeded.scalars(select(LegalTextVersion).where(LegalTextVersion.origin == "eli")).all()
    assert texts
    for tv in texts:
        from_pdf = (tv.parser_version or "").endswith("+pdf")
        good = not from_pdf and tv.parse_quality is not None and tv.parse_quality >= threshold
        assert tv.review_state == ("zaakceptowany" if good else "do_kontroli"), tv.journal_display
    # Każdy tekst — także z PDF — ma jednostki, więc człowiek porównuje odczyt, a nie przepisuje tekst.
    assert all(
        seeded.scalar(select(LegalUnitVersion.id).where(LegalUnitVersion.text_version_id == tv.id))
        for tv in texts
    )
    assert seeded.scalar(select(SyncRun).where(SyncRun.status == "wstrzymany")) is None


@needs_recording
@pytest.mark.parametrize(
    "path",
    sorted((RECORDED / "acts").rglob("text.html")) if RECORDED_INDEX.exists() else [],
    ids=lambda p: str(p.relative_to(RECORDED)),
)
def test_parser_finds_units_in_every_recorded_text(path: Path) -> None:
    result = parse_units(path.read_text(encoding="utf-8"))
    assert result.units, result.issues
    # Wynik jakości trafia do raportu; o publikacji decyduje próg w synchronizacji (test wyżej).
    print(f"{path.relative_to(RECORDED)}: jakość {result.quality}, jednostek {len(result.units)}")
