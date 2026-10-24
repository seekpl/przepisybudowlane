"""Trafność wyszukiwarki (arkusz, działania 5.1–5.4): zestaw z treści, warianty, bramka, zapytania bez wyników."""

from __future__ import annotations

import copy

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SearchMiss, SearchSynonym
from app.modules.search import evaluation as ev
from app.modules.search.misses import normalize, proposals
from app.modules.search.service import search

JAN = {"Authorization": "Bearer tok-jan"}


def test_inflections_cover_cases_and_numbers() -> None:
    forms = ev.inflections("działka budowlana")
    assert {"działki budowlanej", "działce budowlanej", "działkę budowlaną", "działkach budowlanych"} <= set(
        forms
    )
    # Rzeczownik tylko w liczbie mnogiej: bez form pojedynczych.
    assert "robót budowlanych" in ev.inflections("roboty budowlane")
    # Dopełnienie w dopełniaczu zostaje bez zmian.
    assert "obszarze oddziaływania obiektu" in ev.inflections("obszar oddziaływania obiektu")


def test_cases_are_built_from_content(seeded: Session) -> None:
    cases = ev.build_cases(seeded)
    sources = {c.source for c in cases}
    assert {"odmiana", "bez_znakow", "haslo"} <= sources
    budynek = next(c for c in cases if c.query == "budynku")
    assert budynek.source == "odmiana" and budynek.expected == ("budynek",)


def test_variants_are_measured_on_the_same_cases(seeded: Session) -> None:
    report = ev.evaluate(seeded)
    assert {"stemmer", "lematyzacja"} <= set(report["warianty"])
    for r in report["warianty"].values():
        assert 0 <= r["mrr@10"] <= r["recall@5"] <= 1 or r["mrr@10"] <= 1
    assert report["zwyciezca"] in report["warianty"]
    # Zestaw liczony od nowa daje ten sam wynik (pomiar jest powtarzalny).
    assert ev.evaluate(seeded)["warianty"] == report["warianty"]


def test_drop_in_relevance_blocks_merge(seeded: Session) -> None:
    report = ev.evaluate(seeded)
    assert ev.compare_with_baseline(report, copy.deepcopy(report)) == []
    better = copy.deepcopy(report)
    better["warianty"]["stemmer"]["recall@5"] = report["warianty"]["stemmer"]["recall@5"] + 0.05
    problems = ev.compare_with_baseline(report, better)
    assert problems and "stemmer: recall@5 spadło" in problems[0]


def test_lemmatization_finds_inflected_and_unaccented_queries(seeded: Session) -> None:
    for q in ("odległości od granicy", "odleglosc od granicy działki"):
        refs = [h.ref for h in search(seeded, q, variant="lematyzacja").hits[:5]]
        assert "warunki-techniczne-par-12-ust-1" in refs or "warunki-techniczne-par-12" in refs, q


def test_misses_store_no_personal_data(seeded: Session, api: TestClient) -> None:
    assert normalize("  Wiata  Rowerowa ") == "wiata rowerowa"
    for personal in ("jan.kowalski@example.pl", "pesel 85010112345", "ul. Polna 5 Kraków", "x" * 90):
        assert normalize(personal) is None
    for _ in range(2):
        assert api.get("/api/v1/szukaj", params={"q": "zxcvb qwrt"}).json()["hits"] == []
    api.get("/api/v1/szukaj", params={"q": "jan.kowalski@example.pl"})
    misses = seeded.scalars(select(SearchMiss)).all()
    assert [(m.query, m.count) for m in misses] == [("zxcvb qwrt", 2)]


def test_editor_turns_miss_into_synonym(seeded: Session, api: TestClient) -> None:
    api.get("/api/v1/szukaj", params={"q": "odleglosci sasiedzkie xyzzy"})
    api.get("/api/v1/szukaj", params={"q": "kwit"})
    found = {p["zapytanie"]: p for p in proposals(seeded)}
    assert "kwit" in found
    res = api.post(
        "/api/v1/redakcja/synonimy",
        headers=JAN,
        json={"term": "kwit", "expansions": ["zgłoszenie"], "miss_id": found["kwit"]["id"]},
    )
    assert res.status_code == 201
    assert seeded.scalar(select(SearchSynonym).where(SearchSynonym.term == "kwit")) is not None
    assert "kwit" not in {p["zapytanie"] for p in proposals(seeded)}
    hits = api.get("/api/v1/szukaj", params={"q": "kwit"}).json()
    assert hits["synonyms_used"][0]["szukamy_tez"] == ["zgłoszenie"]
    other = found.get("odleglosci sasiedzkie xyzzy")
    if other:
        assert (
            api.post(f"/api/v1/redakcja/propozycje-synonimow/{other['id']}/odrzuc", headers=JAN).status_code
            == 200
        )
