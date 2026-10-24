"""Walidatory szkicu AI bez AI (arkusz, działanie 3.4).

Zdanie przechodzi tylko wtedy, gdy:
- ma co najmniej jeden cytat, każdy cytat wskazuje akapit z podanych i występuje w nim dosłownie;
- każda liczba, data i odesłanie (art., §, ust., pkt, lit.) ze zdania występuje w cytowanych akapitach
  (odesłanie może też być etykietą cytowanego akapitu).

Zdania, które nie przejdą, nie trafiają do szkicu — recenzent widzi je osobno, z powodem odrzucenia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.drafting.sources import Fragment

MONTHS = (
    "stycznia",
    "lutego",
    "marca",
    "kwietnia",
    "maja",
    "czerwca",
    "lipca",
    "sierpnia",
    "września",
    "października",
    "listopada",
    "grudnia",
)
# Liczba nieprzyklejona do litery z lewej („m2” to jednostka, nie liczba), z częścią dziesiętną.
_NUMBER = re.compile(r"(?<![^\W\d_])\d+(?:[.,]\d+)?")
_DATE_WORDS = re.compile(r"\b\d{1,2}\s+(?:" + "|".join(MONTHS) + r")\s+\d{4}\b")
_DATE_DOTS = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b")
_REFERENCE = re.compile(r"(art\.|§|ust\.|pkt|lit\.|poz\.)\s*(\d+[a-z]*|[a-z]{1,2}\b)", re.IGNORECASE)
_DASHES = str.maketrans({"–": "-", "—": "-", "‑": "-", "„": '"', "”": '"', "“": '"', "\u00a0": " "})
MIN_QUOTE_CHARS = 10


@dataclass
class Quote:
    fragment_id: str
    text: str


@dataclass
class Sentence:
    text: str
    quotes: list[Quote]
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def normalize(text: str) -> str:
    return " ".join(text.translate(_DASHES).lower().split())


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUMBER.findall(text)}


def _references(text: str) -> set[str]:
    return {f"{kind.lower()} {num.lower()}" for kind, num in _REFERENCE.findall(normalize(text))}


def check_sentence(sentence: Sentence, sources: dict[str, Fragment]) -> Sentence:
    errors: list[str] = []
    cited: list[Fragment] = []
    if not sentence.quotes:
        errors.append("Zdanie bez cytatu z przepisu.")
    for q in sentence.quotes:
        fragment = sources.get(q.fragment_id)
        if fragment is None:
            errors.append(f"Cytat wskazuje akapit spoza przepisu ({q.fragment_id}).")
            continue
        quote = normalize(q.text).strip(" .,;:")
        if len(quote) < MIN_QUOTE_CHARS:
            errors.append(f"Cytat z {fragment.label} jest za krótki, żeby go sprawdzić.")
        elif quote not in normalize(fragment.text):
            errors.append(f"Cytatu nie ma dosłownie w {fragment.label}: „{q.text.strip()}”.")
        cited.append(fragment)

    source_text = " ".join(f.text for f in cited)
    source_norm = normalize(source_text)
    labels = " ".join(f.label for f in cited)
    missing_numbers = sorted(_numbers(sentence.text) - _numbers(f"{source_text} {labels}"))
    if cited and missing_numbers:
        errors.append("Liczby spoza cytowanego tekstu: " + ", ".join(missing_numbers) + ".")
    for date in _DATE_WORDS.findall(normalize(sentence.text)) + _DATE_DOTS.findall(sentence.text):
        if normalize(date) not in source_norm:
            errors.append(f"Daty „{date}” nie ma w cytowanym tekście.")
    allowed_refs = _references(f"{source_text} {labels}")
    missing_refs = sorted(_references(sentence.text) - allowed_refs)
    if cited and missing_refs:
        errors.append("Odesłania spoza cytowanego tekstu: " + ", ".join(missing_refs) + ".")
    sentence.errors = errors
    return sentence


def check(sentences: list[Sentence], fragments: list[Fragment]) -> list[Sentence]:
    by_id = {f.id: f for f in fragments}
    return [check_sentence(s, by_id) for s in sentences]
