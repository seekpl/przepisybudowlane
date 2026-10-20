# Przepisy budowlane w jednym miejscu

Aplikacja webowa (PWA), która pokazuje obowiązujące przepisy budowlane: **oficjalny tekst z jawnym typem i datą,
na którą jest aktualny, oraz objaśnienie prostym językiem**. Dla inwestorów (tryb prosty, telefon) i pracowników
organów administracji architektoniczno-budowlanej i nadzoru budowlanego (tryb ekspercki, komputer).

Zbudowana według dwóch dokumentów:

- **Plan aplikacji** „Przepisy budowlane w jednym miejscu” (18.10.2026) — zakres MVP, model czasu prawnego,
  synchronizacja z ELI, proces redakcyjny, architektura, testy i blokady wydania.
- **Identyfikacja** „Przepisy budowlane” (system projektowy, 19.10.2026) — tokeny, kroje PB Sans/Serif/Mono,
  komponenty, znak, rysunki techniczne, ton komunikatów. Kopia w [`design/`](design/).

> **Prototyp.** Objaśnienia, kreator i ścieżki są treściami demonstracyjnymi i nie przeszły recenzji prawnej.
> Aplikacja oznacza je w interfejsie. Szczegóły: [`docs/stan-prac.md`](docs/stan-prac.md).

## Co jest w środku

| Obszar | Gdzie | Co robi |
|---|---|---|
| Backend (modułowy monolit) | [`backend/`](backend/) | FastAPI + PostgreSQL: rejestr aktów, adapter ELI, archiwum z SHA-256, parser jednostek, wersje append-only, silnik statusów aktualności, obieg redakcyjny, wyszukiwarka FTS z synonimami, publiczne API (OpenAPI) |
| Frontend (PWA) | [`frontend/`](frontend/) | Next.js 15 + React 19 + TypeScript; komponenty z identyfikacji; tryb prosty i ekspercki; motyw jasny i ciemny |
| Identyfikacja | [`design/`](design/) | `tokens.json` (źródło `frontend/app/tokens.css`), brand book, profil UX |
| Dokumentacja | [`docs/`](docs/) | Architektura, stan prac, decyzje otwarte |

Funkcje MVP z planu: wyszukiwarka (polska odmiana, wpisywanie bez polskich znaków, jawny słownik synonimów),
karta przepisu (tekst, typ, metryka, oficjalny link, stan prawny, wykryte nowelizacje, objaśnienie z datą
weryfikacji, trwały adres każdej wersji), ostrzeżenia o aktualności, kreator „pozwolenie, zgłoszenie czy nic?”,
ścieżki krok po kroku, słowniczek, „Kopiuj cytat”, „Zgłoś błąd” z terminem obsługi, panel stanu danych,
panel redakcji.

## Szybki start (Docker)

```bash
docker compose up --build
```

- aplikacja: <http://localhost:3000>
- API i jego dokumentacja: <http://localhost:8000/docs>
- panel redakcji: <http://localhost:3000/redakcja> (tokeny w `PB_EDITOR_TOKENS`, domyślnie tylko do testów lokalnych)

Kontener `worker` co godzinę synchronizuje akty z ELI API Kancelarii Sejmu (wymaga dostępu do `api.sejm.gov.pl`).

## Uruchomienie bez Dockera

Wymagane: PostgreSQL 16, Python 3.12+ z [uv](https://docs.astral.sh/uv/), Node.js 22.

```bash
# backend
cd backend
uv sync
export PB_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/przepisy
uv run python -m app.cli migrate && uv run python -m app.cli seed
uv run uvicorn app.main:app --port 8000

# frontend (drugi terminal)
cd frontend
npm ci
BACKEND_URL=http://localhost:8000 npm run dev
```

## Testy

```bash
cd backend && uv run pytest            # 84 testy: stan prawny, parser, ELI, synchronizacja, redakcja, API
cd frontend && npm run lint && npm run typecheck && npm run build
cd frontend && npx playwright test     # 26 testów E2E na działającej aplikacji, w tym axe (WCAG 2.1 AA)
```

CI (`.github/workflows/ci.yml`) uruchamia lint, typy, zgodność migracji z modelem, testy backendu, build
frontendu, sprawdza, czy `tokens.css` odpowiada `design/tokens.json`, i odpala testy E2E na złożonej aplikacji.

## Zasady, których pilnuje kod

- **Źródło oficjalne zawsze pierwsze** — każdy przepis prowadzi do aktu w Dzienniku Ustaw.
- **Jawny typ i data** — tekst ogłoszony, jednolity, własna kompilacja albo typ nierozpoznany; „aktualność
  potwierdzona” tylko z podstawą i zakresem potwierdzenia.
- **Awaria nie udaje świeżości** — po przekroczeniu progu (domyślnie 72 h bez udanej synchronizacji lub
  weryfikacji) karta mówi „Nie potwierdzono aktualności”; offline aplikacja nie pokazuje zapamiętanego tekstu.
- **Maszyna wykrywa, człowiek zatwierdza** — synchronizacja tworzy zadania i zawiesza objaśnienia zmienionych
  przepisów; publikuje dopiero niezależny recenzent (autor nie zatwierdza własnej treści).
- **Historii nie nadpisujemy** — wersje tekstów, jednostek i objaśnień są tylko dopisywane.
