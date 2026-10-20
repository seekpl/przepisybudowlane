# Backend — Przepisy budowlane

Modułowy monolit: FastAPI + SQLAlchemy 2 + PostgreSQL 16 (Full Text Search) + Alembic.
Opis architektury i decyzji: [`../docs/architektura.md`](../docs/architektura.md).

## Uruchomienie lokalne

Wymagane: Python 3.12+, [uv](https://docs.astral.sh/uv/), PostgreSQL 16.

```bash
uv sync
export PB_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/przepisy
uv run python -m app.cli migrate      # schemat bazy
uv run python -m app.cli seed         # manifest aktów + treści startowe (idempotentne)
uv run uvicorn app.main:app --reload  # API na http://localhost:8000, dokumentacja: /docs
```

Synchronizacja z ELI (wymaga dostępu do `api.sejm.gov.pl`):

```bash
uv run python -m app.cli sync     # jeden przebieg
uv run python -m app.cli worker   # co PB_SYNC_INTERVAL_MINUTES, z ponawianiem i checkpointem
```

Nagranie prawdziwych odpowiedzi ELI do testów kontraktu:

```bash
uv run python -m app.cli eli-record DU/1994/414 DU/2026/524 --out tests/fixtures/eli/recorded
```

## Konfiguracja (zmienne środowiskowe)

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `PB_DATABASE_URL` | `postgresql+psycopg://postgres@localhost:5432/przepisy` | Baza PostgreSQL |
| `PB_ELI_BASE_URL` | `https://api.sejm.gov.pl/eli` | ELI API Kancelarii Sejmu |
| `PB_ARCHIVE_DIR` | `backend/var/archive` | Archiwum surowych odpowiedzi (SHA-256); w produkcji magazyn w UE |
| `PB_FRESHNESS_THRESHOLD_HOURS` | `72` | Po tylu godzinach bez potwierdzenia karta mówi „Nie potwierdzono aktualności” |
| `PB_SYNC_INTERVAL_MINUTES` | `60` | Odstęp przebiegów workera |
| `PB_PARSER_QUALITY_THRESHOLD` | `0.98` | Poniżej — tekst idzie do kontroli człowieka |
| `PB_REPORT_SLA_WORKING_DAYS` | `5` | Termin obsługi zgłoszenia błędu |
| `PB_EDITOR_TOKENS` | — | `imię=rola1+rola2:token;…` — tymczasowo, do czasu OIDC |
| `PB_CORS_ORIGINS` | `http://localhost:3000` | Dozwolone źródła |

## Testy i jakość

```bash
createdb przepisy_test
PB_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/przepisy_test uv run pytest
uv run ruff check app tests migrations && uv run ruff format --check app tests migrations
uv run mypy
uv run alembic check   # migracje zgodne z modelem
```

Najważniejsze są testy stanu prawnego (`tests/test_freshness.py`) — ich przypadki i oczekiwane
wyniki musi zatwierdzić prawnik, zanim staną się blokadą wydania.
