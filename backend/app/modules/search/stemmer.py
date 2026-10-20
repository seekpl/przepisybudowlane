"""Lekki stemmer polski dla wyszukiwarki.

PostgreSQL nie ma wbudowanego słownika polszczyzny. Zanim zespół podłączy słownik Ispell/Hunspell
i zmierzy trafność (plan, „Architektura techniczna”), indeks i zapytanie przechodzą przez tę samą,
prostą normalizację:
1. małe litery i zdjęcie polskich znaków — „plot” znajdzie „płot”, „dzialka” — „działkę”,
2. ucięcie typowych końcówek fleksyjnych (najdłuższa pasująca, temat co najmniej 3 litery),
3. ruchome „e”: „budynek” → „budynk” (jak w „budynku”).

To przybliżenie — dlatego słownik synonimów jest jawny i testowany, a wyniki można zmierzyć.
"""

from __future__ import annotations

import re
import unicodedata

_FOLD = str.maketrans({"ł": "l", "Ł": "l"})
_TOKEN = re.compile(r"[0-9a-z]+")

# Końcówki po zdjęciu znaków diakrytycznych, od najdłuższych.
_SUFFIXES = sorted(
    {
        "owaniami",
        "owaniach",
        "owaniem",
        "owaniu",
        "owania",
        "owanie",
        "owan",
        "eniami",
        "eniach",
        "eniem",
        "eniu",
        "enia",
        "enie",
        "aniami",
        "aniach",
        "aniem",
        "aniu",
        "ania",
        "anie",
        "osciami",
        "osciach",
        "oscia",
        "osci",
        "osc",
        "iami",
        "iach",
        "iego",
        "iemu",
        "iem",
        "ie",
        "ami",
        "ach",
        "owi",
        "ow",
        "om",
        "em",
        "ego",
        "emu",
        "ymi",
        "imi",
        "ych",
        "ich",
        "iej",
        "ej",
        "ym",
        "im",
        "a",
        "e",
        "i",
        "o",
        "u",
        "y",
    },
    key=len,
    reverse=True,
)

# Słowa, które przez ucięcie końcówki zlałyby się z innymi albo straciły sens.
_KEEP = {"pkt", "art", "ust", "lit", "poz", "dz", "wz", "mpzp", "pinb", "winb", "gunb", "kpa", "eli", "nsa"}


def fold(text: str) -> str:
    text = text.translate(_FOLD).lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(fold(text))


def stem(token: str) -> str:
    w = fold(token)
    if len(w) <= 3 or w in _KEEP or w.isdigit():
        return w
    # Dopełniacz l.mn. rzeczowników na „-enie”: „ogrodzeń” → „ogrodz” (jak „ogrodzenie”).
    if token.lower().endswith("eń") and len(w) >= 6:
        return w[:-2]
    for suffix in _SUFFIXES:
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            break
    if len(w) >= 5 and w.endswith("ek"):
        w = w[:-2] + "k"
    return w


def stems(text: str) -> list[str]:
    return [stem(t) for t in tokens(text)]
