"""Status aktualności przepisu — od spokojnego do alarmowego:

potwierdzona → zmiana (w drodze) → przejściowa (utracił moc, stosowany przejściowo) → niepotwierdzona → zawieszona.

Zasady:
- „Aktualność potwierdzona” pada tylko z podstawą (synchronizacja albo weryfikacja człowieka) i jej zakresem.
- Brak potwierdzenia dłużej niż próg (np. awaria ELI) daje „Nie potwierdzono” — awaria nie udaje świeżości.
- Nowelizacja późniejsza niż stan prawny tekstu: przed wejściem w życie „zmiana”, po — „nie potwierdzono”.
- Typ nierozpoznany nigdy nie dostaje etykiety „aktualny”.
Funkcja ``evaluate`` jest czysta (bez bazy) — testy stanu prawnego podają jej gotowe dane.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from app.models import TextType, ValidityKind
from app.texts import short_date, words_date

SEVERITY = {"potwierdzona": 0, "zmiana": 1, "przejsciowa": 2, "niepotwierdzona": 3, "zawieszona": 4}


@dataclass(frozen=True)
class Reason:
    status: str
    code: str
    title: str
    body: str
    date: dt.date | None = None
    effective_date: dt.date | None = None


@dataclass(frozen=True)
class Interval:
    kind: str
    valid_from: date | None
    valid_to: date | None = None
    title: str | None = None
    description: str | None = None
    basis: str | None = None

    def active_on(self, day: date) -> bool:
        return (self.valid_from is None or self.valid_from <= day) and (
            self.valid_to is None or day <= self.valid_to
        )


@dataclass(frozen=True)
class Amendment:
    eli: str
    journal: str
    published_on: date | None
    entry_into_force: date | None


@dataclass(frozen=True)
class Confirmation:
    at: datetime
    scope: str


@dataclass
class FreshnessInput:
    now: datetime
    today: date
    threshold: timedelta
    text_type: str | None
    legal_status_date: date | None
    incorporated: frozenset[str] = frozenset()
    sync_ok: datetime | None = None
    verification: Confirmation | None = None
    intervals: list[Interval] = field(default_factory=list)
    amendments: list[Amendment] = field(default_factory=list)
    unit_missing_from: str | None = None  # publikator najnowszego tekstu, w którym jednostki już nie ma
    source_paused: str | None = None  # tytuł otwartego alarmu źródła (synchronizacja wstrzymana)


@dataclass(frozen=True)
class Freshness:
    status: str
    date: dt.date | None
    effective_date: dt.date | None
    reasons: list[Reason]
    confirmed_at: datetime | None
    confirmation_scope: str | None

    @property
    def notices(self) -> list[Reason]:
        """Komunikaty przed tekstem przepisu: od najpoważniejszego, bez potwierdzenia (ono jest w odznace)."""
        return sorted(
            (r for r in self.reasons if r.status != "potwierdzona"), key=lambda r: -SEVERITY[r.status]
        )


def is_later_than(am: Amendment, status_date: date) -> bool:
    if am.published_on is not None and am.published_on > status_date:
        return True
    return am.entry_into_force is None or am.entry_into_force > status_date


CHECK_OFFICIAL = "Zanim się na nim oprzesz, porównaj go z oficjalnym tekstem — link znajdziesz w metryce."


def evaluate(inp: FreshnessInput) -> Freshness:
    reasons: list[Reason] = []
    day = inp.today

    # 0. Alarm źródła — pierwszy, bo wyjaśnia pozostałe komunikaty (sortowanie powodów jest stabilne).
    if inp.source_paused:
        reasons.append(
            Reason(
                "niepotwierdzona",
                "synchronizacja_wstrzymana",
                "Synchronizacja z oficjalnym źródłem jest wstrzymana",
                "Źródło zmieniło format danych i do czasu sprawdzenia przez zespół nie potwierdzamy "
                "aktualności żadnego przepisu. " + CHECK_OFFICIAL,
            )
        )

    # 1. Podstawa potwierdzenia i wiek danych.
    confirmation: Confirmation | None = None
    if inp.sync_ok is not None:
        confirmation = Confirmation(
            inp.sync_ok, "synchronizacja z ELI: metryka aktu, tekst i lista nowelizacji"
        )
    if inp.verification is not None and (confirmation is None or inp.verification.at > confirmation.at):
        confirmation = inp.verification
    if confirmation is None:
        reasons.append(
            Reason(
                "niepotwierdzona",
                "brak_potwierdzenia",
                "Nie potwierdziliśmy, że ten tekst jest aktualny",
                "Ani synchronizacja z oficjalnym źródłem, ani redakcja nie sprawdziły jeszcze tego tekstu. "
                + CHECK_OFFICIAL,
            )
        )
    elif inp.now - confirmation.at > inp.threshold:
        reasons.append(
            Reason(
                "niepotwierdzona",
                "dane_nieswieze",
                "Nie potwierdziliśmy, że ten tekst jest aktualny",
                f"Ostatnio sprawdziliśmy go {words_date(confirmation.at.date())}, a od tego czasu prawo mogło się zmienić. "
                + CHECK_OFFICIAL,
            )
        )

    # 2. Typ tekstu.
    if inp.text_type is None:
        reasons.append(
            Reason(
                "niepotwierdzona",
                "brak_tekstu",
                "Nie mamy sprawdzonego tekstu tego przepisu",
                "Tekst czeka na kontrolę redakcji. Skorzystaj z oficjalnego tekstu w metryce.",
            )
        )
    elif inp.text_type == TextType.NIEROZPOZNANY:
        reasons.append(
            Reason(
                "niepotwierdzona",
                "typ_nierozpoznany",
                "Nie ustaliliśmy, czym jest ten tekst",
                "Nie wiemy, czy to tekst ogłoszony, jednolity, czy kompilacja, ani na jaki dzień jest aktualny. "
                + CHECK_OFFICIAL,
            )
        )
    if inp.unit_missing_from:
        reasons.append(
            Reason(
                "niepotwierdzona",
                "jednostka_usunieta",
                "Tego przepisu nie ma w najnowszym tekście aktu",
                f"Mógł zostać uchylony albo przenumerowany ({inp.unit_missing_from}). "
                "Pokazujemy ostatnie znane brzmienie. " + CHECK_OFFICIAL,
            )
        )

    # 3. Oś obowiązywania.
    transitional = [
        iv for iv in inp.intervals if iv.kind == ValidityKind.STOSOWANY_PRZEJSCIOWO and iv.active_on(day)
    ]
    for iv in transitional:
        lost = iv.valid_from
        reasons.append(
            Reason(
                "przejsciowa",
                "stosowany_przejsciowo",
                iv.title
                or (f"Ten przepis utracił moc {words_date(lost)}" if lost else "Ten przepis utracił moc"),
                iv.description
                or "Stosuje się go już tylko przejściowo, na warunkach podanych w przepisie przejściowym. "
                "Sprawdź, czy dotyczą Twojej sprawy.",
                date=lost,
            )
        )
    for iv in inp.intervals:
        if iv.kind == ValidityKind.ZAWIESZONY and iv.active_on(day):
            reasons.append(
                Reason(
                    "zawieszona",
                    "tresc_zawieszona",
                    iv.title or "Treść tego przepisu jest zawieszona",
                    iv.description
                    or "Przepisu nie stosuje się w okresie zawieszenia. Nie opieraj na nim decyzji — "
                    "podstawę zawieszenia podajemy w metryce.",
                )
            )
        elif iv.kind == ValidityKind.UTRACIL_MOC and iv.active_on(day) and not transitional:
            reasons.append(
                Reason(
                    "niepotwierdzona",
                    "utracil_moc",
                    f"Ten akt nie obowiązuje od {words_date(iv.valid_from)}"
                    if iv.valid_from
                    else "Ten akt nie obowiązuje",
                    iv.description
                    or "Nie znaleźliśmy przepisu przejściowego, który pozwalałby go stosować. "
                    + CHECK_OFFICIAL,
                )
            )
        elif (
            iv.kind in (ValidityKind.UTRACIL_MOC, ValidityKind.ZAWIESZONY)
            and iv.valid_from
            and iv.valid_from > day
        ):
            what = "utraci moc" if iv.kind == ValidityKind.UTRACIL_MOC else "zostanie zawieszony"
            reasons.append(
                Reason(
                    "zmiana",
                    "zmiana_obowiazywania",
                    f"Ten przepis {what} {words_date(iv.valid_from)}",
                    iv.description or "Do tego dnia obowiązuje tekst pokazany poniżej.",
                    effective_date=iv.valid_from,
                )
            )

    # 4. Nowelizacje późniejsze niż stan prawny tekstu.
    if inp.text_type is not None and inp.text_type != TextType.NIEROZPOZNANY:
        if inp.legal_status_date is None:
            reasons.append(
                Reason(
                    "niepotwierdzona",
                    "brak_stanu_prawnego",
                    "Nie znamy stanu prawnego tego tekstu",
                    "Źródło nie podało, na jaki dzień tekst jest aktualny, więc nie wiemy, "
                    "które nowelizacje zawiera. " + CHECK_OFFICIAL,
                )
            )
        else:
            for am in sorted(inp.amendments, key=lambda a: (a.entry_into_force or date.max, a.eli)):
                if am.eli in inp.incorporated or not is_later_than(am, inp.legal_status_date):
                    continue
                if am.entry_into_force is None:
                    reasons.append(
                        Reason(
                            "niepotwierdzona",
                            "nowelizacja_bez_daty",
                            "Wykryliśmy nowelizację tego aktu",
                            f"Nowelizacja {am.journal} jest późniejsza niż ten tekst, a nie ustaliliśmy, od kiedy obowiązuje. "
                            + CHECK_OFFICIAL,
                        )
                    )
                elif am.entry_into_force > day:
                    reasons.append(
                        Reason(
                            "zmiana",
                            "nowelizacja_w_drodze",
                            f"Akt zmieni się {words_date(am.entry_into_force)}",
                            f"Nowelizacja {am.journal} jest już ogłoszona. Jeszcze nie sprawdziliśmy, czy zmienia ten przepis. "
                            "Poniżej tekst, który obowiązuje dziś.",
                            effective_date=am.entry_into_force,
                        )
                    )
                else:
                    reasons.append(
                        Reason(
                            "niepotwierdzona",
                            "nowelizacja_obowiazuje",
                            "Ten tekst może nie zawierać obowiązującej zmiany",
                            f"Nowelizacja {am.journal} obowiązuje od {words_date(am.entry_into_force)}, a pokazany tekst ma "
                            f"stan prawny na {words_date(inp.legal_status_date)}. " + CHECK_OFFICIAL,
                        )
                    )

    if not reasons:
        assert confirmation is not None
        reasons.append(
            Reason(
                "potwierdzona",
                "potwierdzona",
                "Aktualność potwierdzona",
                f"Sprawdzone {short_date(confirmation.at.date())}: {confirmation.scope}.",
                date=confirmation.at.date(),
            )
        )

    worst = max(reasons, key=lambda r: SEVERITY[r.status])
    status = worst.status
    the_date = worst.date
    effective = None
    if status == "zmiana":
        effective = min(
            r.effective_date for r in reasons if r.status == "zmiana" and r.effective_date is not None
        )
    if status == "potwierdzona" and confirmation is not None:
        the_date = confirmation.at.date()
    return Freshness(
        status=status,
        date=the_date,
        effective_date=effective,
        reasons=reasons,
        confirmed_at=confirmation.at if confirmation else None,
        confirmation_scope=confirmation.scope if confirmation else None,
    )
