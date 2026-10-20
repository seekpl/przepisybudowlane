"""Klucze, etykiety i trwałe adresy jednostek redakcyjnych.

Klucz: ``art_29.ust_1.pkt_1a`` / ``par_12.ust_1`` / ``art_10.par_1``.
Etykieta w formie urzędowej: „art. 29 ust. 1 pkt 1a”, „§ 12 ust. 1”, „art. 10 § 1”.
"""

from __future__ import annotations

_LABELS = {"art": "art.", "par": "§", "ust": "ust.", "pkt": "pkt", "lit": "lit."}


def unit_label(key: str) -> str:
    parts: list[str] = []
    for part in key.split("."):
        kind, _, num = part.partition("_")
        parts.append(f"{_LABELS[kind]} {num}")
    return " ".join(parts)


def unit_slug(act_slug: str, key: str) -> str:
    return f"{act_slug}-" + key.replace(".", "-").replace("_", "-")
