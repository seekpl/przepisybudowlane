"""Przepisy przejściowe aktu uchylającego (arkusz, działanie 2.4): automat szuka, człowiek decyduje."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EditorialTask, LegalUnit
from app.modules.freshness import service as fresh
from app.modules.parser.units import Paragraph, ParsedUnit
from app.modules.sync.transitional import find_transitional

JAN = {"Authorization": "Bearer tok-jan"}  # recenzent
ANNA = {"Authorization": "Bearer tok-anna"}  # redaktor


def _unit(key: str, *texts: str) -> ParsedUnit:
    return ParsedUnit(key=key, label=key, paragraphs=[Paragraph("", t) for t in texts])


def test_candidates_refer_to_basis_and_speak_about_further_application() -> None:
    units = {
        "art_44": _unit("art_44", "W ustawie w art. 7 ust. 2 pkt 1 otrzymuje brzmienie: „…”."),
        "art_66": _unit(
            "art_66", "1. Dotychczasowe przepisy wydane na podstawie art. 7 ust. 2 pkt 1 zachowują moc."
        ),
        "art_66.ust_1": _unit(
            "art_66.ust_1", "Dotychczasowe przepisy wydane na podstawie art. 7 ust. 2 pkt 1 zachowują moc."
        ),
        "art_70": _unit("art_70", "Do spraw wszczętych stosuje się przepisy dotychczasowe."),
        "art_71": _unit(
            "art_71",
            "Rozporządzenie w sprawie warunków technicznych, jakim powinny odpowiadać budynki i ich usytuowanie "
            "stosuje się do dnia 31 grudnia 2027 r.",
        ),
    }
    found = find_transitional(
        units,
        basis=["art. 7 ust. 2 pkt 1"],
        repealed_title="Rozporządzenie Ministra Infrastruktury z dnia 12 kwietnia 2002 r. w sprawie warunków "
        "technicznych, jakim powinny odpowiadać budynki i ich usytuowanie.",
    )
    # Zmiana brzmienia (art. 44) i ogólny przepis bez odesłania (art. 70) to nie kandydaci;
    # z art. 66 zostaje najgłębsza pasująca jednostka.
    assert [c["klucz"] for c in found] == ["art_66.ust_1", "art_71"]


def test_sync_creates_task_with_candidates_for_repealed_act(seeded: Session) -> None:
    task = seeded.scalar(select(EditorialTask).where(EditorialTask.kind == "przepisy_przejsciowe"))
    assert task is not None and task.state == "otwarte"
    assert task.details["akt_uchylajacy"] == "DU/2019/1696"
    assert task.details["od"] == "2026-09-21"
    assert task.details["podstawa"] == ["art. 7 ust. 2 pkt 1"]
    assert [c["klucz"] for c in task.details["kandydaci"]] == ["art_66.ust_1"]


def test_reviewer_records_transitional_application_and_card_shows_it(
    seeded: Session, api: TestClient
) -> None:
    task = seeded.scalar(select(EditorialTask).where(EditorialTask.kind == "przepisy_przejsciowe"))
    body = {
        "valid_from": "2026-09-21",
        "basis": "art. 66 ust. 1 ustawy o zapewnianiu dostępności (Dz.U. 2019 poz. 1696)",
        "title": "Te warunki techniczne utraciły moc, ale stosuje się je przejściowo",
        "description": "Dane testowe: decyzja recenzenta po ocenie przepisu przejściowego.",
        "task_id": task.id,
    }
    url = "/api/v1/redakcja/akty/warunki-techniczne/stosowanie-przejsciowe"
    assert api.post(url, headers=ANNA, json=body).status_code == 403
    res = api.post(url, headers=JAN, json=body)
    assert res.status_code == 201, res.text
    assert res.json()["recorded_by"] == "jan"

    seeded.expire_all()
    assert seeded.get(EditorialTask, task.id).state == "zamkniete"
    unit = seeded.scalar(select(LegalUnit).where(LegalUnit.slug == "warunki-techniczne-par-12-ust-1"))
    f = fresh.for_unit(seeded, unit)
    codes = [r.code for r in f.reasons]
    assert "stosowany_przejsciowo" in codes and "utracil_moc" not in codes
    card = api.get("/api/v1/przepisy/warunki-techniczne-par-12-ust-1").json()
    assert any(n["title"] == body["title"] for n in card["freshness"]["notices"])


def test_real_repealing_act_points_to_its_transitional_provision() -> None:
    """Nagranie z 21.10.2026: WT uchylone na podstawie Dz.U. 2019 poz. 1696 — automat wskazuje art. 66."""
    import json
    from pathlib import Path

    import pytest

    from app.modules.parser.units import parse_units

    rec = Path(__file__).parent / "fixtures" / "eli" / "recorded" / "acts" / "DU"
    html = rec / "2019" / "1696" / "text.html"
    if not html.exists():
        pytest.skip("brak nagrania aktu uchylającego")
    wt = json.loads((rec / "2002" / "690.json").read_text(encoding="utf-8"))
    basis = [r["art"] for r in wt["references"]["Podstawa prawna z art."] if r.get("art")]
    found = find_transitional(
        parse_units(html.read_text(encoding="utf-8")).units, basis=basis, repealed_title=wt["title"]
    )
    art66 = next(c for c in found if c["klucz"] == "art_66")
    assert "art. 7 ust. 2 i 3" in art66["tekst"] and "zachowują moc" in art66["tekst"]
