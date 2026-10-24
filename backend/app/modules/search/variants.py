"""Warianty normalizacji tekstu dla wyszukiwarki (arkusz, działanie 5.2).

- ``stemmer``     — lekki stemmer w Pythonie (``stemmer.py``): bez polskich znaków, ucięte końcówki;
- ``lematyzacja`` — lematy z Morfeusza 2 przy indeksowaniu i w zapytaniu (bez polskich znaków, żeby
                    „dzialka” trafiała w „działka”; nierozpoznane słowo zostaje jak jest);
- ``hunspell``    — słownik Hunspell pl_PL w PostgreSQL (konfiguracja ``pl_hunspell``, obraz ``db/``).

Wariant produkcyjny wybiera pomiar trafności (``evaluation.py``, plik ``trafnosc.json``).
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.search.stemmer import fold, stems

VARIANTS = ("stemmer", "lematyzacja", "hunspell")
_WORD = re.compile(r"[0-9A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+")
HUNSPELL_CONFIG = "pl_hunspell"


@lru_cache(maxsize=1)
def _morfeusz() -> Any:
    import morfeusz2

    return morfeusz2.Morfeusz()


@lru_cache(maxsize=50_000)
def lemmas(word: str) -> tuple[str, ...]:
    """Lematy słowa bez polskich znaków; pusta krotka, gdy Morfeusz słowa nie zna (np. „dzialka”)."""
    found: list[str] = []
    for _, _, (_, lemma, tag, *_rest) in _morfeusz().analyse(word):
        if tag.startswith("ign"):
            continue
        base = fold(lemma.split(":", 1)[0])
        if base and base not in found:
            found.append(base)
    return tuple(found)


def _raw_words(phrase: str) -> list[str]:
    return _WORD.findall(phrase)


def index_terms(variant: str, phrase: str) -> str:
    """Tekst do ``to_tsvector('simple', …)`` dla wariantów liczonych w Pythonie."""
    if variant == "lematyzacja":
        # Lematy i — jako rezerwa dla zapytań bez polskich znaków — tematy ze stemmera.
        out: list[str] = []
        for w in _raw_words(phrase):
            out.extend(lemmas(w.lower()))
            out.extend(stems(w))
        return " ".join(out)
    return " ".join(stems(phrase))


def query_alternatives(variant: str, phrase: str, stopwords: set[str]) -> str:
    """Fragment tsquery dla jednego słowa/frazy zapytania (wszystkie słowa frazy muszą wystąpić)."""
    parts: list[str] = []
    if variant == "lematyzacja":
        for w in _raw_words(phrase):
            if fold(w) in stopwords:
                continue
            forms = lemmas(w.lower())
            if not forms:  # słowo nieznane Morfeuszowi (np. bez polskich znaków) — temat ze stemmera
                parts.extend(f"{st}:*" for st in stems(w))
                continue
            parts.append(forms[0] if len(forms) == 1 else "(" + " | ".join(dict.fromkeys(forms)) + ")")
    else:
        parts = [f"{st}:*" for st in stems(phrase) if fold(st) not in stopwords]
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else "(" + " & ".join(parts) + ")"


def hunspell_available(s: Session) -> bool:
    return bool(
        s.execute(text("SELECT 1 FROM pg_ts_config WHERE cfgname = :n"), {"n": HUNSPELL_CONFIG}).scalar()
    )


def ensure_hunspell(s: Session) -> bool:
    """Tworzy konfigurację ``pl_hunspell``, jeśli serwer ma pliki słownika (obraz ``db/``)."""
    if hunspell_available(s):
        return True
    try:
        with s.begin_nested():
            s.execute(
                text(
                    "CREATE TEXT SEARCH DICTIONARY pl_ispell (TEMPLATE = ispell, DictFile = pl_pl, AffFile = pl_pl)"
                )
            )
            s.execute(text(f"CREATE TEXT SEARCH CONFIGURATION {HUNSPELL_CONFIG} (COPY = simple)"))
            s.execute(
                text(
                    f"ALTER TEXT SEARCH CONFIGURATION {HUNSPELL_CONFIG} ALTER MAPPING FOR "
                    "asciiword, word, hword, hword_part, hword_asciipart, asciihword WITH pl_ispell, simple"
                )
            )
    except Exception:  # brak plików słownika na serwerze — wariant niedostępny
        return False
    return True
