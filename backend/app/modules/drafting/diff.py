"""Różnice dla recenzenta (arkusz, działanie 3.6): brzmienie przepisu po słowach, objaśnienie po zdaniach.

Długie fragmenty bez zmian są skracane — prawnik czyta to, co się zmieniło, a nie całość od nowa.
"""

from __future__ import annotations

import difflib
import re
from typing import Any

SAME, REMOVED, ADDED = "bez_zmian", "usuniete", "dodane"
CONTEXT_WORDS = 8
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[A-ZĄĆĘŁŃÓŚŹŻ„(])")
# Skróty, po których kropka nie kończy zdania („Dz. U.”, „np. Rada”).
_ABBREVIATIONS = ("Dz.", "np.", "m.in.", "tj.", "tzw.", "ok.", "ww.")


def unit_text(content: list[dict[str, str]]) -> str:
    return "\n".join(f"{p.get('unit', '')} {p['text']}".strip() for p in content)


def _shorten(words: list[str]) -> str:
    if len(words) <= 3 * CONTEXT_WORDS:
        return " ".join(words)
    return " ".join(words[:CONTEXT_WORDS]) + " … " + " ".join(words[-CONTEXT_WORDS:])


def words(old: str, new: str) -> list[dict[str, Any]]:
    a, b = old.split(), new.split()
    out: list[dict[str, Any]] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append({"typ": SAME, "tekst": _shorten(a[i1:i2]), "skrot": i2 - i1 > 3 * CONTEXT_WORDS})
            continue
        if i2 > i1:
            out.append({"typ": REMOVED, "tekst": " ".join(a[i1:i2])})
        if j2 > j1:
            out.append({"typ": ADDED, "tekst": " ".join(b[j1:j2])})
    return out


def sentences(text: str) -> list[str]:
    out: list[str] = []
    for paragraph in text.split("\n\n"):
        for piece in _SENTENCE_END.split(" ".join(paragraph.split())):
            if out and out[-1].endswith(_ABBREVIATIONS):
                out[-1] = f"{out[-1]} {piece}"
            elif piece:
                out.append(piece)
    return out


def by_sentence(old: list[str], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Zdania nowego szkicu (z cytatami) na tle poprzedniego objaśnienia."""
    new_texts = [n["tekst"] for n in new]
    out: list[dict[str, Any]] = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new_texts, autojunk=False).get_opcodes():
        if op == "equal":
            out.extend({"typ": SAME, **n} for n in new[j1:j2])
            continue
        out.extend({"typ": REMOVED, "tekst": t, "cytaty": []} for t in old[i1:i2])
        out.extend({"typ": ADDED, **n} for n in new[j1:j2])
    return out
