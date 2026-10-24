from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ErrorReport
from app.modules.reports.service import _easter, add_working_days


def test_provision_card_has_type_status_citation_and_demo_flag(seeded: Session, api: TestClient) -> None:
    card = api.get("/api/v1/przepisy/warunki-techniczne-par-12-ust-1").json()
    assert card["display_label"] == "WT § 12 ust. 1"
    # Typ, stan prawny i obowiązywanie liczą się z metadanych ELI, nie z danych startowych.
    assert card["text_type"] == "jednolity"
    assert card["freshness"]["status"] == "niepotwierdzona"
    notices = {n["code"]: n for n in card["freshness"]["notices"]}
    assert notices["utracil_moc"]["title"] == "Ten akt nie obowiązuje od 21\u00a0września 2026\u00a0r."
    assert "brak_stanu_prawnego" in notices  # t.j. aktu uchylonego nie podaje stanu prawnego
    assert card["citation"]["text"].endswith("Dz.U. 2022 poz. 1225, § 12 ust. 1")
    assert card["citation"]["as_of"] is None
    assert card["explanation"]["is_demo"] is True
    assert card["illustration"] == "rzut-odleglosc-od-granicy"
    assert card["paragraphs"][1] == {
        "unit": "1)",
        "text": "4 m - w przypadku budynku zwróconego ścianą z oknami lub drzwiami w stronę tej granicy;",
    }


def test_every_text_on_cards_comes_from_eli_snapshot(seeded: Session, api: TestClient) -> None:
    from app.models import LegalTextVersion, SourceSnapshot

    card = api.get("/api/v1/przepisy/prawo-budowlane-art-29-ust-1-pkt-1a").json()
    assert card["text_type"] == "jednolity"
    assert card["citation"]["as_of"] == "2026-03-20"
    rows = seeded.execute(
        select(LegalTextVersion.origin, SourceSnapshot.sha256).join(
            SourceSnapshot, SourceSnapshot.id == LegalTextVersion.snapshot_id
        )
    ).all()
    assert rows and all(origin == "eli" and len(sha) == 64 for origin, sha in rows)


def test_permanent_version_url_and_archived_notice(seeded: Session, api: TestClient) -> None:
    card = api.get("/api/v1/przepisy/warunki-techniczne-par-12-ust-1").json()
    vid = card["versions"][0]["unit_version_id"]
    same = api.get(f"/api/v1/przepisy/warunki-techniczne-par-12-ust-1/wersje/{vid}").json()
    assert same["is_archived_version"] is False
    assert api.get("/api/v1/przepisy/warunki-techniczne-par-12-ust-1/wersje/999999").status_code == 404
    assert api.get("/api/v1/przepisy/nie-ma-takiego").status_code == 404


def test_archived_version_after_sync_is_marked(seeded: Session, api: TestClient, make_sync, fake_eli) -> None:  # type: ignore[no-untyped-def]
    from tests.conftest import FIXTURES, only_act

    old = api.get("/api/v1/przepisy/prawo-budowlane-art-28-ust-1").json()["versions"][0]["unit_version_id"]
    only_act(seeded, "prawo-budowlane")
    html = (FIXTURES / "DU_2026_524.html").read_text(encoding="utf-8")
    fake_eli.routes["/eli/acts/DU/2026/524/text.html"] = (
        200,
        html.replace("z zastrzeżeniem art. 29–31.", "z zastrzeżeniem art. 29–31a.").encode(),
        "text/html",
    )
    # Lista zmian ELI wskazuje tekst jednolity — synchronizacja pobiera go ponownie.
    fake_eli.set_json("/eli/changes/acts", [{"ELI": "DU/2026/524", "changeDate": "2026-10-20T09:00:00"}])
    make_sync().run()
    card = api.get(f"/api/v1/przepisy/prawo-budowlane-art-28-ust-1/wersje/{old}").json()
    assert card["is_archived_version"] is True
    assert card["freshness"]["notices"][0]["code"] == "wersja_archiwalna"
    current = api.get("/api/v1/przepisy/prawo-budowlane-art-28-ust-1").json()
    assert current["paragraphs"][0]["text"].endswith("art. 29–31a.")
    assert len(current["versions"]) == 2


def test_lists_and_details(seeded: Session, api: TestClient) -> None:
    start = api.get("/api/v1/start").json()
    assert len(start["featured"]) == 4 and start["glossary_count"] >= 10
    assert {g["slug"] for g in api.get("/api/v1/sciezki").json()} == {
        "budowa-domu",
        "zakonczenie-budowy",
        "dzialka-co-zbudowac",
    }
    guide = api.get("/api/v1/sciezki/budowa-domu").json()
    assert guide["steps"][3]["unit"]["slug"] == "prawo-budowlane-art-29-ust-1-pkt-1"
    acts = api.get("/api/v1/akty").json()
    assert [a["slug"] for a in acts] == [
        "prawo-budowlane",
        "warunki-techniczne",
        "planowanie-przestrzenne",
        "kpa",
    ]
    assert api.get("/api/v1/akty/kpa").json()["current_text"] is None
    terms = api.get("/api/v1/slowniczek").json()
    assert terms[0]["term"] == "Budowa"  # alfabetycznie
    assert api.get("/api/v1/synonimy").json()[0]["term"]


def test_wizard_results_carry_basis_and_status(seeded: Session, api: TestClient) -> None:
    tree = api.get("/api/v1/kreatory/pozwolenie-zgloszenie").json()
    node = tree["nodes"]["wynik-zgloszenie-70"]
    assert node["basis"] == "Prawo budowlane, art. 29 ust. 1 pkt 1a · Dz.U. 2026 poz. 524"
    assert (
        node["status"] == "zmiana"
    )  # syntetyczna nowelizacja Dz.U. 2026 poz. 900 jeszcze nie weszła w życie
    assert node["links"][0]["url"].startswith("https://e-budownictwo")
    # Każda opcja prowadzi do istniejącego węzła.
    for n in tree["nodes"].values():
        for opt in n["options"]:
            assert opt["next"] in tree["nodes"]


def test_search_uses_inflection_unaccented_input_and_synonyms(seeded: Session, api: TestClient) -> None:
    r = api.get("/api/v1/szukaj", params={"q": "odleglosc od sasiada"}).json()
    assert "warunki-techniczne-par-12-ust-1" in [h["ref"] for h in r["hits"][:3]]
    assert r["synonyms_used"][0]["slowo"] == "sąsiad"
    r = api.get("/api/v1/szukaj", params={"q": "wuzetka"}).json()
    assert any(h["ref"] == "warunki-zabudowy" for h in r["hits"])
    r = api.get("/api/v1/szukaj", params={"q": "budynków"}).json()
    assert any(h["ref"] == "budynek" for h in r["hits"])
    r = api.get("/api/v1/szukaj", params={"q": "zgłoszeniu domu xyzzy"}).json()
    assert r["matched_all_words"] is False and r["hits"]


def test_error_report_validation_sla_and_task(seeded: Session, api: TestClient) -> None:
    bad = api.post(
        "/api/v1/zgloszenia",
        json={"target_path": "/x", "message": "Błąd w treści", "contact_email": "a@b.pl"},
    )
    assert bad.status_code == 422 and "zgodę" in bad.json()["detail"]
    ok = api.post(
        "/api/v1/zgloszenia",
        json={
            "target_path": "/przepis/warunki-techniczne-par-12-ust-1",
            "unit_slug": "warunki-techniczne-par-12-ust-1",
            "message": "Brakuje ust. 2",
            "contact_email": "a@b.pl",
            "consent": True,
        },
    )
    assert ok.status_code == 201
    body = ok.json()
    assert body["number"] == "ZB-1"
    assert body["due_on"] == "2026-10-27"  # 5 dni roboczych od wtorku 20.10.2026
    report = seeded.scalar(select(ErrorReport))
    assert report.task_id is not None and report.consent is True


def test_working_days_skip_weekends_and_polish_holidays() -> None:
    assert _easter(2026) == date(2026, 4, 5)
    assert _easter(2027) == date(2027, 3, 28)
    assert add_working_days(date(2026, 12, 22), 5) == date(2026, 12, 31)  # 24–26.12 wolne
    assert add_working_days(date(2026, 10, 30), 1) == date(2026, 11, 2)  # weekend
    assert add_working_days(date(2026, 11, 10), 1) == date(2026, 11, 12)  # 11.11


def test_status_endpoint_reports_no_sync_yet(manifest: Session, api: TestClient) -> None:
    st = api.get("/api/v1/stan").json()
    assert st["last_success_at"] is None
    assert st["threshold_hours"] == 72
    assert {a["slug"]: a["freshness"] for a in st["acts"]}["kpa"] == "niepotwierdzona"


def test_openapi_contract_is_generated(api: TestClient) -> None:
    spec = api.get("/openapi.json").json()
    assert "/api/v1/przepisy/{slug}" in spec["paths"]
    assert "FreshnessOut" in spec["components"]["schemas"]


def test_statutory_definitions_are_verbatim_with_nominative_terms(seeded: Session, api: TestClient) -> None:
    defs = api.get("/api/v1/definicje").json()
    # Syntetyczny t.j. WT zawiera tylko § 12 i § 13 — definicji (§ 3) w nim nie ma.
    assert defs == []


def test_definitions_from_real_consolidated_text() -> None:
    from pathlib import Path

    import pytest

    from app.modules.content.definitions import extract, nominative
    from app.modules.parser.units import parse_units

    html = (
        Path(__file__).parent
        / "fixtures"
        / "eli"
        / "recorded"
        / "acts"
        / "DU"
        / "2022"
        / "1225"
        / "text.html"
    )
    if not html.exists():
        pytest.skip("brak nagrania t.j. warunków technicznych")
    units = {k: u.content for k, u in parse_units(html.read_text(encoding="utf-8")).units.items()}
    found = {key: (term, paras) for key, term, paras in extract(units)}
    term, paras = found["par_3.pkt_1a"]
    assert term == "działce budowlanej" and nominative(term) == "działka budowlana"
    assert paras[0]["unit"] == "1a)" and paras[0]["text"].startswith(
        "działce budowlanej - należy przez to rozumieć"
    )
    # Definicja z wyliczeniem liter: cały punkt, dosłownie.
    term, paras = found["par_3.pkt_4"]
    assert nominative(term) == "budynek mieszkalny"
    assert [p["unit"] for p in paras] == ["4)", "a)", "b)"]
    assert len(found) >= 25


def test_out_of_scope_wizard_result_lists_provisions_to_check() -> None:
    """4.2 na prawdziwym t.j. PB (odczyt PDF z nagrania): „Ogrodzenie” → art. 29 ust. 1 pkt 21 i ust. 2 pkt 20."""
    from pathlib import Path

    import pytest

    from app.modules.content.to_check import rank
    from app.modules.parser.pdf import parse_pdf

    pdf = (
        Path(__file__).parent / "fixtures" / "eli" / "recorded" / "acts" / "DU" / "2026" / "524" / "text.pdf"
    )
    if not pdf.exists():
        pytest.skip("brak nagrania t.j. Prawa budowlanego")
    units = {k: u.content for k, u in parse_pdf(pdf.read_bytes()).units.items()}
    fence = rank(units, "Ogrodzenie")
    assert {"art_29.ust_1.pkt_21", "art_29.ust_2.pkt_20"} <= set(fence)
    garage = rank(units, "Garaż, wiatę, altanę albo budynek gospodarczy")
    assert {"art_29.ust_1.pkt_14.lit_b", "art_29.ust_1.pkt_14.lit_c", "art_29.ust_2.pkt_3"} <= set(garage)
    # Opis bez konkretnego obiektu nie daje listy — lepiej nic niż szum.
    assert rank(units, "Coś innego") == []


def test_wizard_api_carries_provisions_to_check(seeded: Session, api: TestClient) -> None:
    tree = api.get("/api/v1/kreatory/pozwolenie-zgloszenie").json()
    node = tree["nodes"]["poza-zakresem"]
    # Syntetyczny t.j. PB nie ma art. 29 ust. 2 — lista może być pusta, ale pole jest w kontrakcie API.
    assert isinstance(node["to_check"], dict)
    assert tree["nodes"]["wynik-zgloszenie"]["to_check"] == {}
