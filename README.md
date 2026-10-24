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
| Backend (modułowy monolit) | [`backend/`](backend/) | FastAPI + PostgreSQL: rejestr aktów, adapter ELI z kontraktem i alarmem, archiwum z SHA-256, parser jednostek (HTML i PDF), wersje append-only, silnik statusów aktualności, obieg redakcyjny, szkice objaśnień AI z cytatami do recenzji, wyszukiwarka FTS z lematyzacją i synonimami, publiczne API (OpenAPI) |
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

Kontener `worker` co godzinę synchronizuje akty z ELI API Kancelarii Sejmu (wymaga dostępu do `api.sejm.gov.pl`)
i po każdej synchronizacji dokańcza treści startowe. Tekstu prawa nie ma w danych startowych — do pierwszej
synchronizacji karty przepisów są puste i mówią to wprost.

### Szkice objaśnień AI (opcjonalnie)

Gdy zmieni się brzmienie przepisu z opublikowanym objaśnieniem, objaśnienie jest zawieszane, a system zleca
szkic nowego. Szkic pisze Claude wyłącznie z tekstu z ELI; każde zdanie ma cytat sprawdzany automatycznie.
Szkic trafia do kolejki w panelu redakcji — publikuje go recenzent z nazwiska, nigdy automat.

```bash
export ANTHROPIC_API_KEY=…          # klucz Claude API (czyta go SDK Anthropic)
uv run python -m app.cli szkice-ai  # jeden przebieg: szkice z otwartych zadań „szkic AI”
# albo w workerze: PB_AI_DRAFTS=true (model: PB_AI_MODEL, wysiłek: PB_AI_EFFORT)
```

Bez klucza wszystko działa jak dotąd — zadania „szkic AI” czekają, a objaśnienie może napisać redaktor.

## Uruchomienie bez Dockera

Wymagane: PostgreSQL 16, Python 3.12+ z [uv](https://docs.astral.sh/uv/), Node.js 22.

```bash
# backend
cd backend
uv sync
export PB_DATABASE_URL=postgresql+psycopg://postgres@localhost:5432/przepisy
uv run python -m app.cli migrate
uv run python -m app.cli seed --manifest-only     # manifest aktów
uv run python -m app.cli sync                     # tekst prawa z ELI (bez sieci: --replay tests/fixtures/eli/recorded)
uv run python -m app.cli seed                     # treści startowe przypięte do jednostek z ELI
uv run uvicorn app.main:app --port 8000

# frontend (drugi terminal)
cd frontend
npm ci
BACKEND_URL=http://localhost:8000 npm run dev
```

## Testy

```bash
cd backend && uv run pytest            # stan prawny, parser, ELI i kontrakt, synchronizacja, redakcja, API
cd frontend && npm run lint && npm run typecheck && npm run build
cd frontend && npx playwright test     # 28 testów E2E na działającej aplikacji, w tym axe (WCAG 2.1 AA)
```

CI (`.github/workflows/ci.yml`) uruchamia lint, typy, zgodność migracji z modelem, testy backendu, build
frontendu, sprawdza, czy `tokens.css` odpowiada `design/tokens.json`, i odpala testy E2E na złożonej aplikacji.

Workflow `.github/workflows/eli-nagrania.yml` codziennie nagrywa odpowiedzi prawdziwego ELI API i sprawdza
na nich kontrakt; gdy dane się zmieniły, a testy przechodzą, sam otwiera i scala PR, a gdy kontrakt pada —
otwiera zgłoszenie z etykietą `alarm-eli` (wymaga zgody w ustawieniach repozytorium: *Actions → General →
Allow GitHub Actions to create and approve pull requests*). Szczegóły:
[`backend/tests/fixtures/eli/README.md`](backend/tests/fixtures/eli/README.md).

## Zasady, których pilnuje kod

- **Źródło oficjalne zawsze pierwsze** — każdy przepis prowadzi do aktu w Dzienniku Ustaw.
- **Jawny typ i data** — tekst ogłoszony, jednolity, własna kompilacja albo typ nierozpoznany; „aktualność
  potwierdzona” tylko z podstawą i zakresem potwierdzenia.
- **Awaria nie udaje świeżości** — po przekroczeniu progu (domyślnie 72 h bez udanej synchronizacji lub
  weryfikacji) karta mówi „Nie potwierdzono aktualności”; offline aplikacja nie pokazuje zapamiętanego tekstu.
- **Maszyna wykrywa, człowiek zatwierdza** — synchronizacja tworzy zadania i zawiesza objaśnienia zmienionych
  przepisów; publikuje dopiero niezależny recenzent (autor nie zatwierdza własnej treści).
- **AI pisze szkice, nie publikuje** — szkic objaśnienia powstaje tylko z tekstu z ELI, każde zdanie ma cytat,
  a liczby, daty i odesłania spoza cytowanego tekstu odrzuca walidator; publikuje recenzent z nazwiska.
- **Historii nie nadpisujemy** — wersje tekstów, jednostek i objaśnień są tylko dopisywane.
