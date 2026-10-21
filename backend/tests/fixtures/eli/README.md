# Odpowiedzi ELI do testów

## `DU_*.json`, `DU_*.html` — dane syntetyczne

Mają kształt odpowiedzi ELI API Kancelarii Sejmu (`/eli/acts/{wydawca}/{rok}/{pozycja}` i `/text.html`)
opisany w dokumentacji, ale nie pochodzą z produkcyjnego API. Służą do testów zachowania synchronizacji
(idempotencja, wykrywanie zmian, awarie, alarm kontraktu). Teksty przepisów w plikach HTML są danymi
testowymi, nie źródłem prawa.

## `recorded/` — nagrania z prawdziwego ELI

Zapisuje je workflow [`eli-nagrania`](../../../../.github/workflows/eli-nagrania.yml): świeża baza
z manifestem, potem prawdziwa synchronizacja przez transport zapisujący (`cli eli-record`). Układ:
ścieżka zasobu względem `…/eli/` (`acts/DU/1994/414.json`, `acts/DU/2026/524/text.html`), `index.json`
z adresem, statusem, SHA-256 i datą nagrania każdej odpowiedzi, `kontrakt.json` z wynikiem przebiegu
i naruszeniami kontraktu oraz `openapi.*`, jeśli ELI udostępnia specyfikację.

Na nagraniach działają testy z `tests/test_eli_contract.py` (schemat, zamknięty słownik powiązań,
`legalStatusDate` tekstu jednolitego, parser z progiem jakości, pełna synchronizacja w odtworzeniu).
Lokalnie można odtworzyć synchronizację bez sieci:

```bash
uv run python -m app.cli sync --replay tests/fixtures/eli/recorded
```

Nagrywanie z własnego komputera (wymaga dostępu do `api.sejm.gov.pl` i bazy bez historii synchronizacji):

```bash
uv run python -m app.cli migrate && uv run python -m app.cli seed --manifest-only
uv run python -m app.cli eli-record
```
