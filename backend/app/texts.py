"""Formatowanie po polsku: daty w odznakach i metryce (d.mm.rrrr), słownie w zdaniach."""

from __future__ import annotations

from datetime import date

_MONTHS_GEN = [
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
]

NBSP = " "


def short_date(d: date | None) -> str | None:
    """„20.09.2026”, „1.01.2027” — dzień bez zera wiodącego, miesiąc z zerem."""
    if d is None:
        return None
    return f"{d.day}.{d.month:02d}.{d.year}"


def words_date(d: date | None) -> str | None:
    """„20 września 2026 r.” — do zdań. Spacje niełamiące wiążą liczbę z miesiącem i rok z „r.”."""
    if d is None:
        return None
    return f"{d.day}{NBSP}{_MONTHS_GEN[d.month - 1]} {d.year}{NBSP}r."


def journal(year: int, position: int) -> str:
    return f"Dz.U. {year} poz. {position}"


def journal_from_eli(eli: str) -> str:
    """„DU/2026/524” → „Dz.U. 2026 poz. 524”."""
    parts = eli.split("/")
    if len(parts) == 3 and parts[0] == "DU" and parts[1].isdigit() and parts[2].isdigit():
        return journal(int(parts[1]), int(parts[2]))
    return eli


def plural(n: int, one: str, few: str, many: str) -> str:
    if n == 1:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many
