"""Wyszukiwarka: PostgreSQL Full Text Search na znormalizowanych tematach + jawny słownik synonimów.

Indeks (``search_document``) jest pochodny: przebudowujemy go z treści opublikowanych i zaakceptowanych
tekstów po seedzie, synchronizacji i publikacji. Zapytanie przechodzi przez ten sam stemmer co indeks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import delete, func, literal_column, select, text
from sqlalchemy.orm import Session

from app.models import (
    DecisionTree,
    Explanation,
    GlossaryTerm,
    Guide,
    LegalAct,
    LegalUnit,
    SearchDocument,
    SearchSynonym,
)
from app.modules.editorial.workflow import public_version
from app.modules.freshness.service import current_text, unit_text
from app.modules.search.stemmer import fold, stem, stems, tokens

STOPWORDS = {
    "a",
    "aby",
    "albo",
    "ale",
    "bez",
    "by",
    "co",
    "czy",
    "dla",
    "do",
    "gdy",
    "i",
    "ile",
    "jak",
    "jaka",
    "jaki",
    "jakie",
    "jest",
    "juz",
    "lub",
    "ma",
    "mam",
    "moge",
    "mozna",
    "na",
    "nad",
    "nie",
    "o",
    "od",
    "po",
    "pod",
    "przy",
    "przez",
    "sie",
    "sa",
    "ta",
    "tak",
    "ten",
    "to",
    "u",
    "w",
    "we",
    "z",
    "za",
    "ze",
    "zeby",
    "musze",
    "potrzebuje",
    "trzeba",
    "moj",
    "moja",
    "moje",
    "mojej",
    "mojego",
}

KIND_LABELS = {
    "przepis": "Przepis",
    "pojecie": "Słowniczek",
    "sciezka": "Krok po kroku",
    "kreator": "Kreator",
    "akt": "Akt",
}


@dataclass
class Hit:
    kind: str
    kind_label: str
    ref: str
    title: str
    subtitle: str | None
    snippet: str
    url: str
    rank: float


@dataclass
class SearchResult:
    query: str
    hits: list[Hit]
    synonyms_used: list[dict[str, object]] = field(default_factory=list)
    matched_all_words: bool = True


# --- indeks ---------------------------------------------------------------------------------


@dataclass
class _Doc:
    kind: str
    ref: str
    title: str
    subtitle: str | None
    body: str
    url: str


def _collect(s: Session) -> list[_Doc]:
    docs: list[_Doc] = []
    acts = {a.id: a for a in s.scalars(select(LegalAct))}
    explained = set(s.scalars(select(Explanation.unit_id)))
    for unit in s.scalars(select(LegalUnit).order_by(LegalUnit.id)):
        # Karty wyróżnione, objaśnione i całe artykuły/paragrafy; ustępy i punkty są w treści artykułu.
        if not (unit.featured or unit.id in explained or "." not in unit.unit_key):
            continue
        ut = unit_text(s, unit)
        if ut.unit_version is None:
            continue
        act = acts[unit.act_id]
        body = " ".join(f"{p.get('unit', '')} {p.get('text', '')}".strip() for p in ut.unit_version.content)
        explanation = s.scalar(select(Explanation).where(Explanation.unit_id == unit.id))
        if explanation is not None:
            pv = public_version(explanation.versions)
            if pv is not None and pv.state == "opublikowany":
                body = f"{pv.body} {body}"
        docs.append(
            _Doc(
                "przepis",
                unit.slug,
                unit.title or f"{act.short_title}, {unit.label}",
                f"{act.short_title}, {unit.label}",
                body,
                f"/przepis/{unit.slug}",
            )
        )
    for term in s.scalars(select(GlossaryTerm)):
        tv = public_version(term.versions)
        if tv is None or tv.state != "opublikowany":
            continue
        docs.append(
            _Doc(
                "pojecie", term.slug, tv.term_label, tv.basis_label, tv.definition, f"/slowniczek#{term.slug}"
            )
        )
    for guide in s.scalars(select(Guide)):
        gv = public_version(guide.versions)
        if gv is None or gv.state != "opublikowany":
            continue
        steps = " ".join(f"{st.get('title', '')} {st.get('body', '')} {st.get('who', '')}" for st in gv.steps)
        docs.append(
            _Doc("sciezka", guide.slug, gv.title, None, f"{gv.summary} {steps}", f"/sciezki/{guide.slug}")
        )
    for tree in s.scalars(select(DecisionTree)):
        trv = public_version(tree.versions)
        if trv is None or trv.state != "opublikowany":
            continue
        parts = [trv.intro or ""] + [
            f"{n.question or ''} {n.result_title or ''} {n.result_body or ''}" for n in trv.nodes
        ]
        docs.append(_Doc("kreator", tree.slug, trv.title, None, " ".join(parts), f"/kreator/{tree.slug}"))
    for act in acts.values():
        text_version = current_text(s, act.id)
        docs.append(
            _Doc(
                "akt",
                act.slug,
                act.short_title,
                text_version.journal_display if text_version else None,
                f"{act.title} {act.area}",
                f"/akty/{act.slug}",
            )
        )
    return docs


def rebuild_index(s: Session) -> int:
    s.execute(delete(SearchDocument))
    docs = _collect(s)
    for d in docs:
        title_stems = " ".join(stems(f"{d.title} {d.subtitle or ''}"))
        body_stems = " ".join(stems(d.body))
        tsv = func.setweight(func.to_tsvector(text("'simple'"), title_stems), literal_column("'A'")).op("||")(
            func.setweight(func.to_tsvector(text("'simple'"), body_stems), literal_column("'C'"))
        )
        s.add(
            SearchDocument(
                kind=d.kind, ref=d.ref, title=d.title, subtitle=d.subtitle, body=d.body, url=d.url, tsv=tsv
            )
        )
    s.flush()
    return len(docs)


# --- zapytanie ------------------------------------------------------------------------------


def _synonyms(s: Session) -> dict[str, SearchSynonym]:
    """Klucz to tematy słów hasła — „sąsiada” i „sąsiadem” trafiają w hasło „sąsiad”."""
    return {" ".join(stems(syn.term)): syn for syn in s.scalars(select(SearchSynonym))}


def _alternatives(phrase: str) -> str:
    parts = [f"{st}:*" for st in stems(phrase) if fold(st) not in STOPWORDS]
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else "(" + " & ".join(parts) + ")"


def build_query(s: Session, q: str) -> tuple[list[str], list[dict[str, object]]]:
    """Zwraca grupy tsquery (jedna na słowo zapytania, z synonimami) i listę użytych synonimów."""
    toks = [t for t in tokens(q) if t not in STOPWORDS]
    keys = [stem(t) for t in toks]
    syn = _synonyms(s)
    groups: list[str] = []
    used: list[dict[str, object]] = []
    i = 0
    while i < len(toks):
        bigram = f"{keys[i]} {keys[i + 1]}" if i + 1 < len(toks) else None
        if bigram and bigram in syn:
            term, span = syn[bigram], 2
        elif keys[i] in syn:
            term, span = syn[keys[i]], 1
        else:
            term, span = None, 1
        own = " ".join(toks[i : i + span])
        alts = [_alternatives(own)]
        if term is not None:
            alts += [_alternatives(e) for e in term.expansions]
            used.append({"slowo": term.term, "szukamy_tez": term.expansions})
        alts = [a for a in dict.fromkeys(alts) if a]
        if alts:
            groups.append("(" + " | ".join(alts) + ")")
        i += span
    return groups, used


# Zdanie kończy się kropką, średnikiem lub dwukropkiem, po którym idzie wielka litera — „np. przez” to nie koniec.
_SENTENCE = re.compile(r"(?<=[.;:!?])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„])")


def _snippet(body: str, q_stems: set[str], limit: int = 220) -> str:
    sentences = _SENTENCE.split(body.strip())
    best = next(
        (x for x in sentences if q_stems.intersection(stem(t) for t in tokens(x))),
        sentences[0] if sentences else "",
    )
    best = best.strip()
    return best if len(best) <= limit else best[: limit - 1].rsplit(" ", 1)[0] + "…"


def search(s: Session, q: str, limit: int = 20) -> SearchResult:
    groups, used = build_query(s, q)
    if not groups:
        return SearchResult(query=q, hits=[], synonyms_used=used)
    all_words = True
    hits = _run(s, " & ".join(groups), limit)
    if not hits and len(groups) > 1:
        all_words = False
        hits = _run(s, " | ".join(groups), limit)
    q_stems = {st for st in stems(q) if st not in STOPWORDS}
    for exp in used:
        for e in exp["szukamy_tez"]:  # type: ignore[attr-defined]
            q_stems.update(stems(e))
    result = []
    for doc, rank in hits:
        result.append(
            Hit(
                doc.kind,
                KIND_LABELS[doc.kind],
                doc.ref,
                doc.title,
                doc.subtitle,
                _snippet(doc.body, q_stems),
                doc.url,
                float(rank),
            )
        )
    return SearchResult(query=q, hits=result, synonyms_used=used, matched_all_words=all_words)


def _run(s: Session, tsquery: str, limit: int) -> list[tuple[SearchDocument, float]]:
    query = func.to_tsquery(text("'simple'"), tsquery)
    rank = func.ts_rank_cd(SearchDocument.tsv, query)
    rows = s.execute(
        select(SearchDocument, rank.label("rank"))
        .where(SearchDocument.tsv.op("@@")(query))
        .order_by(rank.desc(), SearchDocument.kind, SearchDocument.title)
        .limit(limit)
    ).all()
    return [(r[0], r[1]) for r in rows]
