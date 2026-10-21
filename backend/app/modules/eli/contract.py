"""Kontrakt z ELI API: co musi być w odpowiedzi, żeby synchronizacja mogła jej zaufać.

Naruszenie kontraktu (zmiana schematu, nieznany klucz powiązania, brak stanu prawnego tekstu
jednolitego) nie jest zwykłym błędem jednego aktu: oznacza, że nasze rozumienie danych mogło
przestać być prawdziwe. Synchronizacja produkcyjna wtedy się wstrzymuje, a karty pokazują
„Nie potwierdzono aktualności”, dopóki człowiek nie zareaguje na alarm (arkusz, działania 1.3–1.5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.modules.eli.schemas import REFERENCE_ROLES, ActMetadata

# Klucze powiązań, które znamy, ale z których synchronizacja nie korzysta. Słownik jest zamknięty:
# klucz spoza ROLES i tej listy to alarm. Listę potwierdza test kontraktu na nagraniach z ELI.
IGNORED_REFERENCE_KEYS: frozenset[str] = frozenset(
    {
        "Akty zmienione",
        "Akty uchylone",
        "Akty uznane za uchylone",
        "Akty wykonawcze z art.",
        "Podstawa prawna",
        "Podstawa prawna z art.",
        "Orzeczenie TK",
        "Odesłania",
        "Inf. o uchyleniu",
        "Inf. o zmianie",
    }
)

KNOWN_REFERENCE_KEYS: frozenset[str] = (
    frozenset(k for keys in REFERENCE_ROLES.values() for k in keys) | IGNORED_REFERENCE_KEYS
)


@dataclass(frozen=True)
class Violation:
    code: str
    message: str


def check_metadata(raw: bytes | str | dict[str, Any], *, consolidated_text: bool = False) -> list[Violation]:
    """Sprawdza jedną odpowiedź metadanych. Pusta lista = odpowiedź zgodna z kontraktem."""
    try:
        data = json.loads(raw) if isinstance(raw, (bytes, str)) else raw
    except ValueError as exc:
        return [Violation("json", f"Odpowiedź nie jest poprawnym JSON-em: {exc}")]
    if not isinstance(data, dict):
        return [Violation("json", "Odpowiedź metadanych nie jest obiektem JSON")]
    violations: list[Violation] = []
    try:
        meta = ActMetadata.model_validate(data)
    except ValidationError as exc:
        fields = sorted({".".join(str(p) for p in e["loc"]) for e in exc.errors()})
        return [Violation("schemat", f"Pola niezgodne ze schematem: {', '.join(fields)}")]

    references = data.get("references") or {}
    unknown = sorted(set(references) - KNOWN_REFERENCE_KEYS)
    if unknown:
        violations.append(
            Violation(
                "nieznany_klucz_powiazania", f"{meta.eli}: nieznane klucze powiązań: {', '.join(unknown)}"
            )
        )
    if consolidated_text and meta.legal_status_date is None:
        violations.append(
            Violation("brak_stanu_prawnego", f"{meta.eli}: tekst jednolity bez pola legalStatusDate")
        )
    return violations


class ContractViolationError(Exception):
    def __init__(self, url: str, violations: list[Violation]) -> None:
        self.url = url
        self.violations = violations
        super().__init__("; ".join(v.message for v in violations))
