"""Reguły kreatora z wyliczeń art. 29 Prawa budowlanego (arkusz, działanie 4.1).

Automat czyta każdy punkt art. 29 ust. 1 (budowa na zgłoszenie) i ust. 2 (bez pozwolenia i zgłoszenia)
i zapisuje go jako regułę: jaki obiekt, przy jakich warunkach (progi liczbowe, liczba obiektów na działce,
położenie) i co wtedy wymagane — z odesłaniem do punktu. Reguła jest tylko propozycją: do kreatora trafia
po zatwierdzeniu przez recenzenta. Gdy tekst się zmienia, reguła punktu o niezmienionym brzmieniu
zachowuje zatwierdzenie; reguła punktu o nowym brzmieniu wraca do kolejki.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

SECTIONS = {"art_29.ust_1": "zgloszenie", "art_29.ust_2": "bez_zgloszenia"}
REQUIREMENT_LABEL = {
    "zgloszenie": "nie wymaga pozwolenia na budowę, ale wymaga zgłoszenia",
    "bez_zgloszenia": "nie wymaga pozwolenia na budowę ani zgłoszenia",
}

_NUMBER = r"(?P<num>\d+(?:,\d+)?)"
_UNIT = r"(?P<unit>m²|m³|m|kWh|kV|MPa|MW|t|stanowisk)"
_MEASURE = (
    r"(?P<what>powierzchni(?: zabudowy| użytkowej| dachu)?|wysokości(?: piętrzenia)?|głębokości|pojemności"
    r"(?: nominalnej)?|długości(?: całkowitej)?|rozpiętości(?: konstrukcji| elementów konstrukcyjnych)?"
    r"|wydajności|napięcie znamionowe|ciśnieniu roboczym|przekroju wewnętrznym|mocy)"
)
_UPPER = (
    r"do|niewiększ\w* niż|nieprzekraczając\w*|niewyższ\w* niż|nie większ\w* niż|nie wyższ\w* niż"
    r"|niewięcej niż|nie więcej niż"
)
_LOWER = r"powyżej|większ\w* niż|przekraczając\w*|wyższ\w* niż|równej lub przekraczającej"
_CONDITION = re.compile(rf"{_MEASURE}[^;,–]*?\b(?P<cmp>{_UPPER}|{_LOWER})\s+{_NUMBER}\s*{_UNIT}")
_AND_BOUND = re.compile(rf",?\s*ale\s+(?P<cmp>{_UPPER}|{_LOWER})\s+{_NUMBER}\s*{_UNIT}")
_LEAD_MEASURE = re.compile(rf",?\s+o\s+{_MEASURE}:?$")
_PER_PLOT = re.compile(
    r"liczba[^;]*?(?:nie może przekraczać|nie może być większa niż)\s+(?P<count>\w+)\s+na każde\s+"
    r"(?P<area>[\d\s]+)\s*m² powierzchni działki"
)
_WORDS_TO_INT = {"jeden": 1, "jednego": 1, "dwóch": 2, "dwa": 2, "trzech": 3, "pięć": 5, "5": 5}
_LOCATION = [
    (
        re.compile(r"obszar oddziaływania mieści się w całości na działce"),
        "obszar oddziaływania w całości na działce",
    ),
    (
        re.compile(r"z wyjątkiem [^;]*obszarze Natura 2000|z wyjątkiem sytuowanych na obszarze Natura 2000"),
        "poza obszarem Natura 2000",
    ),
    (re.compile(r"sytuowanych na obszarze Natura 2000"), "na obszarze Natura 2000"),
    (re.compile(r"terenach zamkniętych"), "na terenach zamkniętych"),
    (
        re.compile(r"na działce, na której znajduje się budynek mieszkalny"),
        "na działce z budynkiem mieszkalnym",
    ),
    (re.compile(r"przy budynkach mieszkalnych jednorodzinnych"), "przy domu jednorodzinnym"),
]


@dataclass
class Rule:
    unit_key: str
    requirement: str
    object_text: str
    conditions: list[dict[str, Any]] = field(default_factory=list)


def _comparator(cmp: str) -> str:
    return "max" if re.fullmatch(_UPPER, cmp) else "min"


def _object(text: str) -> str:
    """Obiekt to początek punktu do pierwszego warunku („ogrodzeń o wysokości …” → „ogrodzeń”)."""
    m = re.split(
        r"\s+(?:o |–|-|,|których|przeznaczonych|służących|sytuowanych|położonych|wraz|w rozumieniu)",
        text,
        maxsplit=1,
    )
    return m[0].strip(" ,;:.")


def _conditions(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for m in _CONDITION.finditer(text):
        found.append(
            {
                "typ": m.group("what"),
                "porownanie": _comparator(m.group("cmp")),
                "wartosc": float(m.group("num").replace(",", ".")),
                "zapis": m.group("num"),
                "jednostka": m.group("unit"),
            }
        )
        # „powyżej 35 m², ale niewięcej niż 70 m²” — drugi próg tej samej wielkości.
        if (more := _AND_BOUND.match(text, m.end())) is not None:
            found.append(
                {
                    "typ": m.group("what"),
                    "porownanie": _comparator(more.group("cmp")),
                    "wartosc": float(more.group("num").replace(",", ".")),
                    "zapis": more.group("num"),
                    "jednostka": more.group("unit"),
                }
            )
    per = _PER_PLOT.search(text)
    count = _WORDS_TO_INT.get(per.group("count")) if per is not None else None
    if per is not None and count is not None:
        found.append(
            {
                "typ": "liczba obiektów na działce",
                "porownanie": "max",
                "wartosc": count,
                "na_m2": int(per.group("area").replace(" ", "")),
            }
        )
    for pattern, label in _LOCATION:
        if pattern.search(text):
            found.append({"typ": "położenie", "wartosc": label})
            if label == "poza obszarem Natura 2000":
                break
    return found


def extract(units: dict[str, list[dict[str, str]]]) -> list[Rule]:
    """Reguły z najgłębszych jednostek art. 29 ust. 1–2.

    Litera dostaje obiekt z wprowadzenia punktu („wolno stojących” + „garaży”) i część wspólną po
    ostatniej literze („– o powierzchni zabudowy do 35 m², przy czym …”), bo ta dotyczy wszystkich liter.
    """
    common: dict[str, str] = {}
    for key, content in units.items():
        if ".lit_" in key and " – " in content[-1]["text"]:
            pkt = key.rsplit(".", 1)[0]
            siblings = sorted(k for k in units if k.startswith(pkt + ".lit_"))
            if siblings and siblings[-1] == key:
                common[pkt] = content[-1]["text"].split(" – ", 1)[1]
    rules = []
    for key, content in units.items():
        section = ".".join(key.split(".")[:2])
        if section not in SECTIONS or key == section or any(o.startswith(key + ".") for o in units):
            continue
        item = content[-1]["text"]
        if ".lit_" in key:
            pkt = key.rsplit(".", 1)[0]
            lead = next((p["text"] for p in content if p["unit"].endswith(")") and p is not content[-1]), "")
            own = item.split(" – ", 1)[0] if pkt in common else item
            measure = _LEAD_MEASURE.search(lead.rstrip(":"))
            if measure is not None:
                # „budynków rekreacji indywidualnej, o powierzchni zabudowy: a) do 35 m²” — litera to próg.
                obj = _object(lead[: measure.start()])
                text = f"{measure.group('what')} {own} {common.get(pkt, '')}"
            else:
                obj = f"{lead.rstrip(':')} {_object(own)}".strip()
                text = f"{own} {common.get(pkt, '')}"
        else:
            obj, text = _object(item), item
        rules.append(
            Rule(unit_key=key, requirement=SECTIONS[section], object_text=obj, conditions=_conditions(text))
        )
    return rules


_MEASURE_NOM = {
    "powierzchni": "powierzchnia",
    "powierzchni zabudowy": "powierzchnia zabudowy",
    "powierzchni użytkowej": "powierzchnia użytkowa",
    "powierzchni dachu": "powierzchnia dachu",
    "wysokości": "wysokość",
    "wysokości piętrzenia": "wysokość piętrzenia",
    "głębokości": "głębokość",
    "pojemności": "pojemność",
    "pojemności nominalnej": "pojemność nominalna",
    "długości": "długość",
    "długości całkowitej": "długość całkowita",
    "rozpiętości": "rozpiętość",
    "rozpiętości konstrukcji": "rozpiętość konstrukcji",
    "rozpiętości elementów konstrukcyjnych": "rozpiętość elementów konstrukcyjnych",
    "wydajności": "wydajność",
    "ciśnieniu roboczym": "ciśnienie robocze",
    "przekroju wewnętrznym": "przekrój wewnętrzny",
    "mocy": "moc",
}


def _objects(n: int) -> str:
    if n == 1:
        return "1 taki obiekt"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} takie obiekty"
    return f"{n} takich obiektów"


def describe(condition: dict[str, Any]) -> str:
    """Warunek po polsku: „wysokość nie więcej niż 2,20 m”."""
    if condition["typ"] == "położenie":
        return str(condition["wartosc"])
    if condition["typ"] == "liczba obiektów na działce":
        return f"najwyżej {_objects(int(condition['wartosc']))} na każde {condition['na_m2']} m² działki"
    measure = _MEASURE_NOM.get(condition["typ"], condition["typ"])
    sign = "nie więcej niż" if condition["porownanie"] == "max" else "więcej niż"
    return f"{measure} {sign} {condition.get('zapis', condition['wartosc'])} {condition['jednostka']}"


# --- zapis propozycji ---------------------------------------------------------------------------------

ACT = "prawo-budowlane"


def propose(s: Any, text_version: Any) -> int:
    """Propozycje reguł dla przyjętego tekstu Prawa budowlanego. Zwraca liczbę nowych propozycji do przeglądu.

    Punkt o niezmienionym brzmieniu (ta sama suma treści) dziedziczy decyzję recenzenta z poprzedniego tekstu.
    """
    from sqlalchemy import select

    from app.clock import now
    from app.models import LegalAct, LegalUnit, LegalUnitVersion, WizardRule

    act = s.get(LegalAct, text_version.act_id)
    if act is None or act.slug != ACT:
        return 0
    if s.scalar(select(WizardRule.id).where(WizardRule.text_version_id == text_version.id).limit(1)):
        return 0
    rows = s.execute(
        select(LegalUnit, LegalUnitVersion)
        .join(LegalUnitVersion, LegalUnitVersion.unit_id == LegalUnit.id)
        .where(LegalUnitVersion.text_version_id == text_version.id, LegalUnit.unit_key.like("art_29.%"))
    ).all()
    by_key = {u.unit_key: (u, uv) for u, uv in rows}
    new = 0
    for rule in extract({k: uv.content for k, (_, uv) in by_key.items()}):
        unit, uv = by_key[rule.unit_key]
        earlier = s.scalar(
            select(WizardRule)
            .where(
                WizardRule.unit_key == rule.unit_key,
                WizardRule.content_hash == uv.content_hash,
                WizardRule.state != "propozycja",
            )
            .order_by(WizardRule.id.desc())
        )
        row = WizardRule(
            act_id=act.id,
            text_version_id=text_version.id,
            unit_id=unit.id,
            unit_key=rule.unit_key,
            content_hash=uv.content_hash,
            requirement=rule.requirement,
            object_text=rule.object_text,
            conditions=rule.conditions,
            state=earlier.state if earlier else "propozycja",
            reviewed_by=f"{earlier.reviewed_by} (brzmienie bez zmian)" if earlier else None,
            reviewed_at=now() if earlier else None,
        )
        s.add(row)
        new += earlier is None
    s.flush()
    return new


def approved_for(s: Any, unit_id: int, content_hash: str) -> Any:
    """Zatwierdzona reguła dla danego brzmienia jednostki albo None."""
    from sqlalchemy import select

    from app.models import WizardRule

    return s.scalar(
        select(WizardRule)
        .where(
            WizardRule.unit_id == unit_id,
            WizardRule.content_hash == content_hash,
            WizardRule.state == "zatwierdzona",
        )
        .order_by(WizardRule.id.desc())
    )
