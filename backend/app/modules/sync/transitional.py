"""Przepisy przejściowe aktu uchylającego (arkusz, działanie 2.4).

Metadane ELI mówią tylko, że akt uchylono i którym aktem („Uchylenia wynikające z”). Czy i do jakich spraw
stosuje się go dalej, wynika z przepisów przejściowych — a ich ocena to interpretacja, więc należy do
człowieka. Automat zawęża pracę: w tekście aktu uchylającego znajduje jednostki, które odsyłają do podstawy
prawnej uchylonego aktu (np. „art. 7 ust. 2 pkt 1”) albo do niego samego i mówią o dalszym stosowaniu.
"""

from __future__ import annotations

import re

from app.modules.parser.units import ParsedUnit

# Słowa, po których poznać przepis o dalszym stosowaniu albo zachowaniu mocy.
_KEEPS_IN_FORCE = re.compile(
    r"zachowuj\w*\s+moc|dotychczasow\w*|stosuje\s+się|stosować\s+się|do\s+dnia\s+wejścia\s+w\s+życie"
)
_WS = re.compile(r"\s+")
MAX_EXCERPT = 1500


def _norm(text: str) -> str:
    return _WS.sub(" ", text.replace("\u00a0", " ")).strip().lower()


def find_transitional(
    units: dict[str, ParsedUnit], *, basis: list[str], repealed_title: str | None = None
) -> list[dict[str, str]]:
    """Kandydaci na przepisy przejściowe: najgłębsze jednostki, które spełniają oba warunki."""
    needles = [_norm(b) for b in basis if b.strip()]
    title = _norm(repealed_title or "")
    # Fragment tytułu bez „Rozporządzenie Ministra … z dnia …” — to, co akt uchylający zwykle przytacza.
    title_core = title.split(" w sprawie ", 1)[1].rstrip(".") if " w sprawie " in title else ""
    matched: dict[str, ParsedUnit] = {}
    for key, unit in units.items():
        text = _norm(" ".join(p["text"] for p in unit.content))
        refers = any(n in text for n in needles) or (bool(title_core) and title_core in text)
        if refers and _KEEPS_IN_FORCE.search(text):
            matched[key] = unit
    deepest = [k for k in matched if not any(other.startswith(k + ".") for other in matched)]
    return [
        {
            "klucz": key,
            "jednostka": matched[key].label,
            "tekst": " ".join(f"{p['unit']} {p['text']}".strip() for p in matched[key].content)[:MAX_EXCERPT],
        }
        for key in deepest
    ]
