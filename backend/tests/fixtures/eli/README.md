# Odpowiedzi ELI do testów

## `DU_*.json`, `DU_*.html` — dane testowe

Odpowiedzi w kształcie ELI API Kancelarii Sejmu (`/eli/acts/{wydawca}/{rok}/{pozycja}` i `/text.html`)
do testów zachowania synchronizacji (idempotencja, wykrywanie zmian, awarie, alarm kontraktu) i fikstury
`seeded` (manifest → synchronizacja → treści, jak na produkcji):

- Prawo budowlane (`DU_1994_414`, `DU_2026_524`, nowelizacje `DU_2025_100`, `DU_2026_900`) — syntetyczne;
  teksty przepisów w HTML są danymi testowymi, nie źródłem prawa;
- warunki techniczne (`DU_2002_690`, `DU_2022_1225`) — metadane odwzorowują nagranie z 21.10.2026
  (akt uznany za uchylony, t.j. bez `legalStatusDate`), a `DU_2022_1225.html` to wycinek nagranego
  HTML (§ 12 i § 13 w oryginalnym układzie ELI);
- akt uchylający WT (`DU_2019_1696`) — metadane jak w ELI, HTML **syntetyczny** (oznaczony
  „[TEKST SYNTETYCZNY]”) do testu wyszukiwania przepisów przejściowych.

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
