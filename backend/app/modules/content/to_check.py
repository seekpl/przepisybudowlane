"""Przepisy do sprawdzenia dla przypadków, których kreator nie obejmuje (arkusz, działanie 4.2).

Gdy kreator mówi „tego przypadku jeszcze nie obejmujemy”, dokładamy listę punktów art. 29 Prawa
budowlanego, które dotyczą wybranego obiektu (garaż, wiata, ogrodzenie…). To nie jest odpowiedź: lista
pokazuje dosłowne brzmienie z przyjętego tekstu z ELI i prowadzi do kart, a ocenę zostawia czytelnikowi
albo urzędowi. Dopasowanie po lematach (Morfeusz 2) z wagą rzadkości słowa w artykule.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LegalAct, LegalUnit, LegalUnitVersion
from app.modules.content.wizard_rules import REQUIREMENT_LABEL, approved_for, describe
from app.modules.freshness.service import current_text
from app.modules.search.stemmer import fold
from app.modules.search.variants import _morfeusz, _raw_words, lemmas

ACT = "prawo-budowlane"
# Budowa obiektów: art. 29 ust. 1 (zgłoszenie) i ust. 2 (bez pozwolenia i zgłoszenia).
SECTIONS = ("art_29.ust_1.", "art_29.ust_2.")
# Słowa z opisów odpowiedzi, które nie mówią nic o obiekcie („albo” Morfeusz zna też jako rzeczownik „alba”).
IGNORED = frozenset({"cos", "inny", "albo", "alba", "lub", "oraz", "i", "na", "do", "w", "z", "o"})
LIMIT = 10


@dataclass(frozen=True)
class ToCheck:
    unit_slug: str
    label: str
    intro: str  # wprowadzenie ustępu („Nie wymaga decyzji … natomiast wymaga zgłoszenia …”)
    paragraphs: list[dict[str, str]]
    # Reguła zatwierdzona przez recenzenta dla tego brzmienia (4.1): wymóg i warunki po polsku.
    rule: dict[str, object] | None = None


def _lemma_set(text: str) -> set[str]:
    return {lemma for w in _raw_words(text.lower()) for lemma in lemmas(w) if lemma not in IGNORED}


def _content_lemmas(query: str) -> set[str]:
    """Lematy rzeczowników i przymiotników z opisu obiektu — bez zaimków („coś”, „czym” → „co”)."""
    out = set()
    for w in _raw_words(query.lower()):
        analyses = _morfeusz().analyse(w)
        end = max((j for _, j, _ in analyses), default=0)
        for i, j, (_, lemma, tag, *_r) in analyses:
            # Tylko odczytania całego słowa: „coś” to nie „co” + „-ś”.
            if (i, j) == (0, end) and tag.split(":")[0] in ("subst", "adj", "ger", "depr"):
                base = fold(lemma.split(":", 1)[0])
                if base not in IGNORED:
                    out.add(base)
    return out


def rank(units: dict[str, list[dict[str, str]]], query: str) -> list[str]:
    """Klucze najgłębszych punktów/liter z ``SECTIONS`` najlepiej pasujących do opisu obiektu."""
    wanted = _content_lemmas(query)
    if not wanted:
        return []
    leaves = [
        k for k in units if k.startswith(SECTIONS) and not any(other.startswith(k + ".") for other in units)
    ]
    own = {k: _lemma_set(" ".join(p["text"] for p in units[k][1:])) for k in leaves}
    df = Counter(lemma for words in own.values() for lemma in words)
    n = max(len(leaves), 1)
    # Punkt musi zawierać choć jedno rzadkie słowo z opisu („garaż”, „ogrodzenie”), nie tylko pospolite
    # („budynek”, „zabudowa”) — inaczej lista byłaby szumem, a nie podpowiedzią.
    specific = {x for x in wanted if 0 < df[x] <= max(8, n // 12)}
    leaves = [k for k in leaves if own[k] & specific]

    # Najpierw punkty z największą liczbą rzadkich słów z opisu, potem z rzadszymi słowami.
    def score(k: str) -> tuple[int, float]:
        return len(own[k] & specific), sum(math.log(n / df[x]) for x in own[k] & wanted)

    return sorted(leaves, key=lambda k: (*(-v for v in score(k)), k))[:LIMIT]


def to_check(s: Session, query: str) -> list[ToCheck]:
    act = s.scalar(select(LegalAct).where(LegalAct.slug == ACT))
    text = current_text(s, act.id) if act else None
    if act is None or text is None:
        return []
    rows = s.execute(
        select(LegalUnit, LegalUnitVersion)
        .join(LegalUnitVersion, LegalUnitVersion.unit_id == LegalUnit.id)
        .where(LegalUnitVersion.text_version_id == text.id, LegalUnit.unit_key.like("art_29.%"))
    ).all()
    by_key = {u.unit_key: (u, uv) for u, uv in rows}
    out = []
    for key in rank({k: uv.content for k, (_, uv) in by_key.items()}, query):
        unit, uv = by_key[key]
        section = ".".join(key.split(".")[:2])
        intro = by_key[section][1].content[0] if section in by_key else {"unit": "", "text": ""}
        approved = approved_for(s, unit.id, uv.content_hash)
        out.append(
            ToCheck(
                unit_slug=unit.slug,
                label=unit.label,
                intro=f"{intro['unit']} {intro['text']}".strip(),
                paragraphs=[p for p in uv.content if p != intro],
                rule={
                    "wymog": REQUIREMENT_LABEL[approved.requirement],
                    "warunki": [describe(c) for c in approved.conditions],
                    "zatwierdzil": approved.reviewed_by,
                }
                if approved
                else None,
            )
        )
    return out
