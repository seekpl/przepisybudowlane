# Architektura

Modułowy monolit, jak rekomenduje plan: jeden backend, jedna relacyjna baza, logicznie rozdzielone moduły,
jedno publiczne API. Bez mikroserwisów, kolejek i osobnego silnika wyszukiwania na starcie.

```
             ┌─────────────── ELI API Kancelarii Sejmu (JSON, HTML, PDF)
             │
   worker ───┤  sync: lista zmian → metadane → tekst → parser → różnice → nowelizacje → zadania
             │        │ surowe odpowiedzi (SHA-256) ──► archiwum (magazyn w UE)
             ▼        ▼
        PostgreSQL 16  ◄──── backend (FastAPI): publiczne API /api/v1, API redakcji, OpenAPI
                                   ▲
                                   │ server-side fetch (bez cache), akcje serwera
                          frontend (Next.js, PWA) ◄──── przeglądarka (tryb prosty / ekspercki)
```

## Moduły backendu (`backend/app/modules`)

| Moduł | Odpowiada za |
|---|---|
| `registry` | Manifest aktów (zatwierdzona lista zamiast listy portali), klucze, etykiety i trwałe adresy jednostek |
| `eli` | Klient ELI z ponawianiem (5xx, 429, przekroczenie czasu; bez ponawiania 4xx), schemat odpowiedzi, role powiązań |
| `archive` | Archiwum surowych odpowiedzi adresowane SHA-256, zapis atomowy, kontrola sumy przy odczycie |
| `parser` | HTML → art./§ → ust. → pkt → lit.; tekst bez zmian poza białymi znakami; ocena jakości |
| `sync` | Idempotentny przebieg z checkpointem, wykrywanie zmian i nowelizacji, zawieszanie zależnych treści |
| `freshness` | Pięć statusów aktualności z powodami (czysta funkcja `evaluate` + odczyt danych z bazy) |
| `editorial` | Stany redakcyjne i ich historia, zadania redakcyjne, flagi zawieszenia węzłów kreatora |
| `search` | Lekki stemmer polski, jawny słownik synonimów, indeks PostgreSQL FTS |
| `reports` | Zgłoszenia błędów: termin w dniach roboczych (z polskimi świętami), e-mail tylko ze zgodą, retencja |
| `content` | Ładowanie manifestu i treści startowych przez prawdziwy obieg redakcyjny |
| `ops` | Panel stanu danych: ostatnia udana synchronizacja, wiek danych, zaległe zadania, błędy pobrań |

## Model danych i czas prawny

Dwie osie czasu (plan, „model czasu prawnego”):

- **czas obowiązywania** — `legal_validity_interval` (obowiązuje, utracił moc, stosowany przejściowo,
  zawieszony; korekta = nowy wiersz z `supersedes_id`), `detected_amendment` (data ogłoszenia i wejścia
  w życie), `legal_text_version.legal_status_date` (deklarowany stan prawny);
- **czas systemowy** — `recorded_at`/`created_at` w każdym wierszu, `source_fetch` (każda próba pobrania,
  także nieudana), `system_history` (dziennik dopisywany).

Tabele z planu (nazwy robocze): `legal_act`, `source_snapshot`, `legal_text_version`, `legal_unit`,
`legal_unit_version`, `legal_validity_interval`, `system_history`, `explanation_version`,
`decision_tree_node_version`, `editorial_event` — oraz pomocnicze: `source_fetch`, `source_verification`,
`detected_amendment`, `editorial_task`, `content_flag`, `guide_version`, `glossary_term_version`,
`error_report`, `sync_run`, `sync_checkpoint`, `search_document`, `search_synonym`.

## Status aktualności

`freshness.engine.evaluate` łączy powody i wybiera najpoważniejszy:

| Status | Kiedy |
|---|---|
| Aktualność potwierdzona | udana synchronizacja z ELI albo ręczna weryfikacja w progu (domyślnie 72 h), znany typ i stan prawny, brak późniejszych nowelizacji |
| Zmiana w drodze | nowelizacja późniejsza niż tekst, jeszcze nieobowiązująca; zapowiedziana utrata mocy |
| Utracił moc, stosowany przejściowo | aktywny przedział „stosowany przejściowo” (np. art. 102a Prawa budowlanego) |
| Nie potwierdzono aktualności | brak potwierdzenia lub dane po progu; typ nierozpoznany; brak stanu prawnego; obowiązująca nowelizacja, której tekst nie zawiera; przepis zniknął z nowego tekstu; wersja archiwalna |
| Treść zawieszona | aktywny przedział „zawieszony” — najsilniejszy sygnał |

Komunikaty stoją przed tekstem przepisu w obu trybach. Każdy ma tytuł i zdanie „co zrobić”.

## Synchronizacja

1. Lista zmian od checkpointu (z zapasem `PB_SYNC_OVERLAP_HOURS`); jej awaria = pełne odświeżenie.
2. Metadane aktu bazowego (walidacja schematu), przedział obowiązywania tylko przy zmianie.
3. Najnowszy tekst jednolity z powiązań; tekst pobierany, gdy zmieniły się metadane, lista zmian go wskazuje
   albo nie ma jeszcze zaakceptowanego tekstu.
4. HTML → parser; jakość poniżej `PB_PARSER_QUALITY_THRESHOLD` albo tylko PDF → kontrola człowieka
   (zadanie), nie publikacja.
5. Porównanie jednostek z poprzednim tekstem; zmienione → nowe wersje, zawieszone objaśnienia i węzły kreatora,
   zadania „zmiana tekstu”.
6. Nowelizacje z okna roku przed stanem prawnym; późniejsze niż tekst → zadanie z terminem = dzień wejścia w życie.
7. Checkpoint przesuwa się tylko po w pełni udanym przebiegu; błędy → zadanie „awaria synchronizacji”.

Idempotencja: migawki unikalne po (URL, SHA-256), wersje tekstu po (akt, migawka), zadania po kluczu deduplikacji.

## Frontend

- Strony renderowane po stronie serwera przy każdym żądaniu (`cache: "no-store"`) — status aktualności nie może
  pochodzić z pamięci podręcznej.
- Tryb w ciasteczku funkcjonalnym; przełącznik i zgłoszenia działają też bez JavaScriptu (akcje serwera).
- Komponenty identyfikacji w `components/ds/`, tokeny generowane z `design/tokens.json`.
- Service worker zapamiętuje tylko zasoby statyczne; bez sieci pokazuje statyczną stronę „Brak połączenia”.

## Bezpieczeństwo i prywatność

- Publiczny odczyt bez konta; jedyne dane osobowe to dobrowolny e-mail w zgłoszeniu (zgoda + retencja).
- API redakcji: tokeny ze zmiennej środowiskowej, porównanie w stałym czasie; do zastąpienia przez OIDC.
- Nagłówki bezpieczeństwa w Next.js; ciasteczko redakcji `httpOnly`, `SameSite=Strict`, ograniczone do `/redakcja`.
