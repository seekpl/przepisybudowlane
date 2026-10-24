"""Pomiar trafności wyszukiwarki (arkusz, działania 5.1–5.3).

Zestaw testowy budujemy maszynowo z treści, którą wyszukiwarka ma znajdować — bez ręcznego wybierania
zapytań, więc nie da się go „dopasować” do jednego wariantu:

- hasła słowniczka i definicje ustawowe w każdej formie odmiany (Morfeusz 2: przypadki × liczby),
  także bez polskich znaków — oczekiwany wynik: hasło albo przepis z definicją;
- tytuły kart przepisów — oczekiwany wynik: ta karta;
- potoczne słowa z jawnego słownika synonimów — oczekiwany wynik: dokumenty, których tytuł zawiera
  rozwinięcie („płot” → wszystko z „ogrodzeniem” w tytule).

Ten sam zestaw liczymy dla trzech wariantów normalizacji (``variants.py``). Wynik zapisany w
``trafnosc.json`` wskazuje zwycięzcę (wariant produkcyjny), a CI nie przepuszcza spadku trafności.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import column, insert, select, table, text
from sqlalchemy.orm import Session

from app.models import GlossaryTerm, SearchSynonym
from app.modules.content.definitions import statutory_definitions
from app.modules.editorial.workflow import public_version
from app.modules.registry.units import unit_slug
from app.modules.search.service import BASELINE, _collect, build_query, document_tsv
from app.modules.search.stemmer import fold, stems
from app.modules.search.variants import VARIANTS, ensure_hunspell

TOP_K = 5
# Tolerancja na szum liczbowy; każdy większy spadek blokuje scalenie (5.3).
TOLERANCE = 0.005
CASES = ("gen", "dat", "acc", "inst", "loc")


@dataclass(frozen=True)
class Case:
    query: str
    expected: tuple[str, ...]
    source: str


@lru_cache(maxsize=1)
def _morfeusz() -> Any:
    import morfeusz2

    return morfeusz2.Morfeusz()


def _analyses(word: str) -> list[tuple[str, list[str]]]:
    return [
        (lemma.split(":", 1)[0], tag.split(":")) for _, _, (_, lemma, tag, *_r) in _morfeusz().analyse(word)
    ]


def _form(lemma: str, pos: str, number: str, case: str, gender: str) -> str | None:
    for form, _, tag, *_r in _morfeusz().generate(lemma):
        p = tag.split(":")
        if p[0] != pos or len(p) < 4 or number not in p[1].split(".") or case not in p[2].split("."):
            continue
        if gender not in p[3].split("."):
            continue
        if pos == "adj" and p[4:5] != ["pos"]:
            continue
        return str(form)
    return None


def inflections(phrase: str) -> list[str]:
    """Formy frazy w mianowniku („działka budowlana”) we wszystkich przypadkach i obu liczbach."""
    words = phrase.lower().split()
    head = None
    for i, w in enumerate(words):
        for lemma, p in _analyses(w):
            if p[0] == "subst" and len(p) >= 4 and "nom" in p[2].split("."):
                head = (i, lemma, p[1].split(".")[0], p[3].split(".")[0], "pt" in p)
                break
        if head:
            break
    if head is None:
        return []
    i, lemma, _number, gender, plurale = head
    adj_lemmas: dict[int, str] = {}
    for j in range(len(words)):
        if j == i:
            continue
        if j > i and j - 1 not in adj_lemmas and j - 1 != i:
            break
        lem = next(
            (lm for lm, p in _analyses(words[j]) if p[0] == "adj" and "nom" in p[2].split(".")),
            None,
        )
        if lem is None:
            if j < i:
                return []
            break
        adj_lemmas[j] = lem
    out: list[str] = []
    for num in ("pl",) if plurale else ("sg", "pl"):
        for case in CASES:
            noun = _form(lemma, "subst", num, case, gender)
            if noun is None:
                continue
            forms = list(words)
            forms[i] = noun
            ok = True
            for j, lem in adj_lemmas.items():
                adj = _form(lem, "adj", num, case, gender)
                if adj is None:
                    ok = False
                    break
                forms[j] = adj
            if ok:
                out.append(" ".join(forms))
    return [f for f in dict.fromkeys(out) if f != phrase.lower()]


def build_cases(s: Session) -> list[Case]:
    docs = _collect(s)
    by_title_stems = [(d.ref, set(stems(d.title))) for d in docs]
    cases: list[Case] = []

    def add_forms(phrase: str, expected: tuple[str, ...], source: str) -> None:
        forms = inflections(phrase)
        for form in forms:
            cases.append(Case(form, expected, "odmiana"))
        for form in [phrase.lower(), *forms[:3]]:
            if fold(form) != form:
                cases.append(Case(fold(form), expected, "bez_znakow"))
        cases.append(Case(phrase.lower(), expected, source))

    for term in s.scalars(select(GlossaryTerm).order_by(GlossaryTerm.slug)):
        tv = public_version(term.versions)
        if tv is not None and tv.state == "opublikowany":
            add_forms(tv.term_label, (term.slug,), "haslo")
    for df in statutory_definitions(s):
        # W indeksie jest cały przepis definicyjny (art. 3, § 3) — to on ma się znaleźć.
        add_forms(df.term, (unit_slug(df.act_slug, df.unit_key.split(".", 1)[0]),), "definicja")
    for d in docs:
        if d.kind == "przepis" and d.title and not d.title.startswith(d.subtitle or "\0"):
            cases.append(Case(d.title.lower(), (d.ref,), "tytul"))
            cases.append(Case(fold(d.title), (d.ref,), "bez_znakow"))
    for syn in s.scalars(select(SearchSynonym).order_by(SearchSynonym.term)):
        wanted = {st for e in syn.expansions for st in stems(e)}
        expected = tuple(ref for ref, title in by_title_stems if wanted & title)
        if expected:
            cases.append(Case(syn.term.lower(), expected, "synonim"))
    unique: dict[str, Case] = {}
    for c in cases:
        if c.query in unique:
            merged = tuple(dict.fromkeys(unique[c.query].expected + c.expected))
            unique[c.query] = Case(c.query, merged, unique[c.query].source)
        else:
            unique[c.query] = c
    return list(unique.values())


def _prepare(s: Session, variants: list[str]) -> None:
    s.execute(text("DROP TABLE IF EXISTS search_eval"))
    columns = ", ".join(f"tsv_{v} tsvector" for v in variants)
    s.execute(text(f"CREATE TEMP TABLE search_eval (ref text, title text, {columns})"))
    tbl = table("search_eval", column("ref"), column("title"), *(column(f"tsv_{v}") for v in variants))
    for d in _collect(s):
        values: dict[str, Any] = {"ref": d.ref, "title": d.title}
        for v in variants:
            values[f"tsv_{v}"] = document_tsv(v, f"{d.title} {d.subtitle or ''}", d.body)
        s.execute(insert(tbl).values(**values))


def _ranked(s: Session, variant: str, query: str) -> list[str]:
    groups, _ = build_query(s, query, variant)
    if not groups:
        return []
    for tsquery in (" & ".join(groups), " | ".join(groups)):
        rows = s.execute(
            text(
                f"SELECT ref FROM search_eval, to_tsquery('simple', :q) AS q WHERE tsv_{variant} @@ q "
                f"ORDER BY ts_rank_cd(tsv_{variant}, q) DESC, title LIMIT 10"
            ),
            {"q": tsquery},
        ).scalars()
        refs = list(rows)
        if refs:
            return refs
    return []


def evaluate(s: Session, cases: list[Case] | None = None) -> dict[str, Any]:
    """Trafność każdego dostępnego wariantu na tym samym zestawie: recall@5 i MRR@10, ogółem i wg źródła."""
    cases = cases if cases is not None else build_cases(s)
    variants = [v for v in VARIANTS if v != "hunspell" or ensure_hunspell(s)]
    _prepare(s, variants)
    results: dict[str, Any] = {}
    for v in variants:
        hits = 0
        rr = 0.0
        by_source: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        misses: list[str] = []
        for c in cases:
            refs = _ranked(s, v, c.query)
            pos = next((i for i, r in enumerate(refs) if r in c.expected), None)
            ok = pos is not None and pos < TOP_K
            hits += ok
            rr += 1 / (pos + 1) if pos is not None else 0.0
            by_source[c.source][0] += ok
            by_source[c.source][1] += 1
            if not ok and len(misses) < 15:
                misses.append(c.query)
        n = max(len(cases), 1)
        results[v] = {
            "recall@5": round(hits / n, 4),
            "mrr@10": round(rr / n, 4),
            "wg_zrodla": {k: round(a / b, 4) for k, (a, b) in sorted(by_source.items())},
            "przyklady_chybien": misses,
        }
    s.execute(text("DROP TABLE IF EXISTS search_eval"))
    winner = max(results, key=lambda v: (results[v]["recall@5"], results[v]["mrr@10"]))
    return {
        "data": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "zestaw": {
            "przypadki": len(cases),
            "zrodla": dict(sorted(_count(c.source for c in cases).items())),
        },
        "warianty": results,
        "niedostepne": [v for v in VARIANTS if v not in results],
        "zwyciezca": winner,
    }


def _count(items: Any) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for i in items:
        out[i] += 1
    return out


def compare_with_baseline(report: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    """Powody, dla których zmiana nie może przejść (5.3). Pusta lista = trafność nie spadła."""
    problems = []
    for v, base in baseline.get("warianty", {}).items():
        now = report["warianty"].get(v)
        if now is None:
            continue  # wariant niedostępny w tym środowisku (np. brak słownika Hunspell)
        for metric in ("recall@5", "mrr@10"):
            if now[metric] < base[metric] - TOLERANCE:
                problems.append(f"{v}: {metric} spadło z {base[metric]} do {now[metric]}")
    if baseline.get("zestaw", {}).get("przypadki") != report["zestaw"]["przypadki"]:
        problems.append(
            f"zestaw testowy zmienił się ({baseline.get('zestaw', {}).get('przypadki')} → "
            f"{report['zestaw']['przypadki']} przypadków) — zapisz nowy pomiar: cli search-eval --zapisz"
        )
    return problems


def save_baseline(report: dict[str, Any]) -> None:
    BASELINE.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cases_json(cases: list[Case]) -> str:
    return json.dumps([asdict(c) for c in cases], ensure_ascii=False, indent=1)
