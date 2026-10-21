"""Słowniczek z definicji ustawowych (arkusz, działanie 3.2): cytat, nie interpretacja.

Z przyjętego tekstu aktu bierzemy przepis definicyjny („Ilekroć w ustawie jest mowa o: 1) budynku – należy
przez to rozumieć …”) i każdy jego punkt pokazujemy dosłownie, z odesłaniem do jednostki. Jedyne, co robi
automat, to sprowadza definiowane pojęcie do mianownika („budynku mieszkalnym” → „budynek mieszkalny”)
słownikiem fleksyjnym Morfeusz 2 — żeby hasło dało się znaleźć w alfabecie. Treść definicji się nie zmienia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LegalAct, LegalUnit, LegalUnitVersion
from app.modules.freshness.service import current_text

_DEFINING_ARTICLE = re.compile(
    r"^(Ilekroć w (ustawie|rozporządzeniu|kodeksie) jest mowa o|Użyte w (ustawie|rozporządzeniu) określenia oznaczają)",
    re.IGNORECASE,
)
_DEFINITION = re.compile(
    r"^(?P<term>.+?)\s+[–-]\s+(?P<verb>należy przez to rozumieć|rozumie się przez to|oznacza)\b"
)
_WORD = re.compile(r"[\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ-]+|\S")


@dataclass(frozen=True)
class Definition:
    term: str  # pojęcie w mianowniku (do alfabetu i wyszukiwania)
    term_in_text: str  # pojęcie tak, jak stoi w przepisie
    paragraphs: list[dict[str, str]]  # dosłowne brzmienie punktu (z literami)
    unit_key: str
    unit_slug: str
    unit_label: str
    act_slug: str
    act_title: str
    journal: str


@lru_cache(maxsize=1)
def _morfeusz() -> Any:
    import morfeusz2

    return morfeusz2.Morfeusz()


def _interpretations(word: str) -> list[tuple[str, str]]:
    return [(lemma.split(":", 1)[0], tag) for _, _, (_, lemma, tag, *_rest) in _morfeusz().analyse(word)]


def _generate(lemma: str, *, pos: str, number: str, gender: str) -> str | None:
    for form, _, tag, *_rest in _morfeusz().generate(lemma):
        parts = tag.split(":")
        if parts[0] != pos or len(parts) < 4 or number not in parts[1].split("."):
            continue
        if pos == "adj" and parts[4:5] != ["pos"]:
            continue  # stopień równy: „właściwy”, nie „właściwszy”
        if "nom" in parts[2].split(".") and gender in parts[3].split("."):
            return str(form)
    return None


def _loc_noun(word: str) -> tuple[str, str, str] | None:
    """(lemat, liczba, rodzaj), jeśli słowo może być rzeczownikiem w miejscowniku."""
    for lemma, tag in _interpretations(word):
        parts = tag.split(":")
        if parts[0] == "subst" and len(parts) >= 4 and "loc" in parts[2].split("."):
            return lemma, parts[1].split(".")[0], parts[3].split(".")[0]
    return None


def _agreeing_adj(word: str, number: str, gender: str) -> str | None:
    for lemma, tag in _interpretations(word):
        parts = tag.split(":")
        if (
            parts[0] == "adj"
            and len(parts) >= 4
            and number in parts[1].split(".")
            and "loc" in parts[2].split(".")
            and gender in parts[3].split(".")
        ):
            return lemma
    return None


def _is_adverb(word: str) -> bool:
    return any(tag.split(":")[0] == "adv" for _, tag in _interpretations(word))


_PL_ORDER = "aąbcćdeęfghijklłmnńoóprsśtuwyzźż"


def polish_key(text: str) -> tuple[int, ...]:
    """Klucz sortowania w polskim alfabecie („ś” po „s”, „ż” na końcu)."""
    return tuple(_PL_ORDER.index(c) if c in _PL_ORDER else 100 + ord(c) for c in text.lower())


def nominative(phrase: str) -> str:
    """„budynku mieszkalnym jednorodzinnym” → „budynek mieszkalny jednorodzinny”; dopełnienia zostają.

    Rzeczownik główny to pierwszy wyraz w miejscowniku; przymiotniki uzgodnione z nim (przed nim i tuż
    po nim) też idą do mianownika. Dalsze wyrazy („oddziaływania obiektu”) zostają bez zmian.
    """
    tokens = phrase.split()
    for i, token in enumerate(tokens):
        head = _loc_noun(token)
        if head is None:
            continue
        lemma, number, gender = head
        before = [_agreeing_adj(t, number, gender) for t in tokens[:i]]
        if any(a is None for a in before):
            continue  # wyraz przed rzeczownikiem nie jest uzgodnionym przymiotnikiem — to nie ten rzeczownik
        out = [
            _generate(a, pos="adj", number=number, gender=gender) or t
            for a, t in zip(before, tokens[:i], strict=True)
            if a
        ]
        out.append(_generate(lemma, pos="subst", number=number, gender=gender) or lemma)
        rest = tokens[i + 1 :]
        for j, t in enumerate(rest):
            adj = _agreeing_adj(t, number, gender)
            if (
                adj is None
                and _is_adverb(t)
                and j + 1 < len(rest)
                and _agreeing_adj(rest[j + 1], number, gender)
            ):
                out.append(t)  # „biologicznie czynnym” — przysłówek zostaje, przymiotnik idzie dalej
                continue
            if adj is None:
                out.extend(rest[j:])
                break
            out.append(_generate(adj, pos="adj", number=number, gender=gender) or t)
        return " ".join(out)
    return phrase


def extract(units: dict[str, list[dict[str, str]]]) -> list[tuple[str, str, list[dict[str, str]]]]:
    """(klucz punktu, pojęcie z przepisu, dosłowne akapity) — z treści jednostek jednego tekstu."""
    found = []
    for key, content in units.items():
        if "." in key or not content or not _DEFINING_ARTICLE.match(content[0]["text"]):
            continue
        for child_key, child in units.items():
            parts = child_key.split(".")
            if child_key.startswith(key + ".") and len(parts) == 2 and parts[1].startswith("pkt_"):
                own = child[1:]  # pierwszy akapit to wprowadzenie wyliczenia („Ilekroć … mowa o:”)
                m = _DEFINITION.match(own[0]["text"]) if own else None
                if m:
                    found.append((child_key, m.group("term").strip(), own))
    return found


def statutory_definitions(s: Session) -> list[Definition]:
    """Definicje z przyjętych tekstów wszystkich aktów manifestu, alfabetycznie."""
    out: list[Definition] = []
    for act in s.scalars(select(LegalAct).order_by(LegalAct.id)):
        text = current_text(s, act.id)
        if text is None:
            continue
        rows = s.execute(
            select(LegalUnit, LegalUnitVersion)
            .join(LegalUnitVersion, LegalUnitVersion.unit_id == LegalUnit.id)
            .where(LegalUnitVersion.text_version_id == text.id)
        ).all()
        by_key = {u.unit_key: (u, uv) for u, uv in rows}
        for key, term, paragraphs in extract({k: uv.content for k, (_, uv) in by_key.items()}):
            unit = by_key[key][0]
            out.append(
                Definition(
                    term=nominative(term),
                    term_in_text=term,
                    paragraphs=paragraphs,
                    unit_key=key,
                    unit_slug=unit.slug,
                    unit_label=unit.label,
                    act_slug=act.slug,
                    act_title=act.short_title,
                    journal=text.journal_display,
                )
            )
    return sorted(out, key=lambda d: (polish_key(d.term), d.act_slug))
