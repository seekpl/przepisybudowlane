"""Akapity przepisu, z których AI pisze objaśnienie — każdy z identyfikatorem i etykietą urzędową."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.registry.units import unit_label

_ART_UST = re.compile(r"^Art\.\s*(\d+[a-z]*)\.\s*(\d+[a-z]*)\.$")
_ART_PAR = re.compile(r"^Art\.\s*(\d+[a-z]*)\.\s*§\s*(\d+[a-z]*)\.$")
_ART = re.compile(r"^Art\.\s*(\d+[a-z]*)\.$")
_PAR_UST = re.compile(r"^§\s*(\d+[a-z]*)\.\s*(\d+[a-z]*)\.$")
_PAR = re.compile(r"^§\s*(\d+[a-z]*)\.$")
_UST = re.compile(r"^(\d+[a-z]*)\.$")
_PKT = re.compile(r"^(\d+[a-z]*)\)$")
_LIT = re.compile(r"^([a-z]{1,2})\)$")

# Poziomy jednostek od najwyższego — niższy poziom zastępuje wszystko pod sobą.
_LEVELS = ("art", "par", "ust", "pkt", "lit")


@dataclass(frozen=True)
class Fragment:
    id: str  # „A1”, „A2”… — tym identyfikatorem AI wskazuje akapit w cytacie
    label: str  # „art. 29 ust. 1 pkt 1”
    text: str


def _set(path: list[tuple[str, str]], kind: str, num: str) -> list[tuple[str, str]]:
    level = _LEVELS.index(kind)
    kept = [(k, n) for k, n in path if _LEVELS.index(k) < level]
    # „§” pod artykułem (k.p.a.) to paragraf artykułu; samodzielny „§” (rozporządzenie) zaczyna ścieżkę.
    if kind == "par" and not any(k == "art" for k, _ in path):
        kept = []
    return [*kept, (kind, num)]


def _path(unit_key: str) -> list[tuple[str, str]]:
    return [(kind, num) for kind, _, num in (part.partition("_") for part in unit_key.split("."))]


def fragments(unit_key: str, content: list[dict[str, str]]) -> list[Fragment]:
    """Akapity jednostki z etykietą jednostki, do której należą (wprowadzenie ustępu, punkt, litera)."""
    root = _path(unit_key)[:1]
    path = list(root)
    out: list[Fragment] = []
    for i, p in enumerate(content, start=1):
        marker = p.get("unit", "").strip()
        if m := _ART_UST.match(marker):
            path = [("art", m[1]), ("ust", m[2])]
        elif m := _ART_PAR.match(marker):
            path = [("art", m[1]), ("par", m[2])]
        elif m := _ART.match(marker):
            path = [("art", m[1])]
        elif m := _PAR_UST.match(marker):
            path = [("par", m[1]), ("ust", m[2])]
        elif m := _PAR.match(marker):
            path = _set(path, "par", m[1])
        elif m := _UST.match(marker):
            path = _set(path, "ust", m[1])
        elif m := _PKT.match(marker):
            path = _set(path, "pkt", m[1])
        elif m := _LIT.match(marker):
            path = _set(path, "lit", m[1])
        key = ".".join(f"{k}_{n}" for k, n in path) or unit_key
        out.append(Fragment(id=f"A{i}", label=unit_label(key), text=p["text"]))
    return out
