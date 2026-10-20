"""Konfiguracja aplikacji — wyłącznie ze zmiennych środowiskowych (prefiks PB_)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Editor:
    """Osoba z redakcji. Do czasu wdrożenia OIDC uwierzytelniana tokenem ze zmiennej środowiskowej."""

    name: str
    roles: frozenset[str]
    token: str

    def can(self, role: str) -> bool:
        return role in self.roles


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PB_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/przepisy"

    # Źródło: oficjalne ELI API Kancelarii Sejmu.
    eli_base_url: str = "https://api.sejm.gov.pl/eli"
    eli_timeout_seconds: float = 20.0
    eli_max_retries: int = 3
    eli_backoff_seconds: float = 1.0

    # Archiwum surowych odpowiedzi (adresowane sumą SHA-256). W produkcji: magazyn w UE.
    archive_dir: Path = BACKEND_DIR / "var" / "archive"

    # Po tylu godzinach bez udanej synchronizacji lub weryfikacji karta mówi „Nie potwierdzono aktualności”.
    freshness_threshold_hours: int = 72
    # Synchronizacja zaczyna od checkpointu cofniętego o ten zapas, żeby nie zgubić zmian z granicy okna.
    sync_overlap_hours: int = 24
    sync_interval_minutes: int = 60
    # Wynik parsera poniżej progu trafia do kontroli człowieka zamiast do publikacji.
    parser_quality_threshold: float = 0.98

    # Termin obsługi zgłoszenia błędu (dni robocze) i retencja adresów e-mail po zamknięciu.
    report_sla_working_days: int = 5
    report_email_retention_days: int = 30

    # Tokeny redakcji: "imię=rola1+rola2:token;imię2=rola:token2". Tymczasowe — do czasu OIDC.
    editor_tokens: str = ""

    # Treści demonstracyjne są oznaczane w interfejsie i nigdy nie udają zatwierdzonych przez prawnika.
    demo_content: bool = True

    cors_origins: str = "http://localhost:3000"

    def editors(self) -> list[Editor]:
        result: list[Editor] = []
        for chunk in filter(None, (c.strip() for c in self.editor_tokens.split(";"))):
            ident, _, token = chunk.partition(":")
            name, _, roles = ident.partition("=")
            if not name or not token or not roles:
                continue
            result.append(
                Editor(
                    name=name.strip(),
                    roles=frozenset(r.strip() for r in roles.split("+")),
                    token=token.strip(),
                )
            )
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
