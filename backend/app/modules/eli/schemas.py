"""Schemat odpowiedzi ELI API (api.sejm.gov.pl/eli) — tylko pola, z których korzystamy.

Pola wymagane są ścisłe: brak któregoś to błąd walidacji widoczny w panelu, a nie cicha luka.
Pozostałe są opcjonalne, a nieznane pola są ignorowane (API może dodawać nowe).

Nazwy kluczy w ``references`` są potwierdzone testem kontraktu na nagraniach z produkcyjnego API
(``tests/fixtures/eli/recorded``, workflow ``eli-nagrania``). Role kluczy są w jednym miejscu:
``REFERENCE_ROLES``; klucz spoza nich i spoza ``contract.IGNORED_REFERENCE_KEYS`` to alarm.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Reference(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    # Pole nazywa się w ELI „date”; nazwa atrybutu nie może zasłaniać typu ``date``.
    on: date | None = Field(default=None, alias="date")
    art: str | None = None


class ActMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    eli: str = Field(alias="ELI")
    publisher: str
    year: int
    pos: int
    title: str
    status: str
    display_address: str | None = Field(default=None, alias="displayAddress")
    type: str | None = None
    in_force: str | None = Field(default=None, alias="inForce")
    promulgation: date | None = None
    announcement_date: date | None = Field(default=None, alias="announcementDate")
    entry_into_force: date | None = Field(default=None, alias="entryIntoForce")
    valid_from: date | None = Field(default=None, alias="validFrom")
    repeal_date: date | None = Field(default=None, alias="repealDate")
    expiration_date: date | None = Field(default=None, alias="expirationDate")
    legal_status_date: date | None = Field(default=None, alias="legalStatusDate")
    change_date: datetime | None = Field(default=None, alias="changeDate")
    text_html: bool = Field(default=False, alias="textHTML")
    text_pdf: bool = Field(default=False, alias="textPDF")
    references: dict[str, list[Reference]] = Field(default_factory=dict)

    @field_validator("eli")
    @classmethod
    def _eli_shape(cls, v: str) -> str:
        parts = v.split("/")
        if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
            raise ValueError(f"Nieoczekiwany identyfikator ELI: {v!r}")
        return v

    @property
    def journal_display(self) -> str:
        return self.display_address or f"Dz.U. {self.year} poz. {self.pos}"

    def refs(self, role: str) -> list[Reference]:
        found: list[Reference] = []
        for key in REFERENCE_ROLES[role]:
            found.extend(self.references.get(key, []))
        return found


class ChangeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    eli: str = Field(alias="ELI")
    change_date: datetime | None = Field(default=None, alias="changeDate")


REFERENCE_ROLES: dict[str, tuple[str, ...]] = {
    # Obwieszczenia o tekście jednolitym — przy akcie bazowym.
    "consolidated_texts": ("Inf. o tekście jednolitym",),
    # Akt, którego tekst jednolity ogłasza obwieszczenie — przy obwieszczeniu.
    "consolidates": ("Tekst jednolity dla aktu",),
    # Akty, które zmieniły ten akt.
    "amended_by": ("Akty zmieniające", "Zmiany wynikające z"),
    # Przy obwieszczeniu: nowelizacje, których tekst jednolity nie zawiera (potwierdzone nagraniem 21.10.2026).
    "amended_after_consolidation": ("Nowelizacje po tekście jednolitym",),
    # Akty, które go uchyliły.
    "repealed_by": ("Akty uchylające", "Uchylenia wynikające z"),
    "executive_acts": ("Akty wykonawcze",),
}
