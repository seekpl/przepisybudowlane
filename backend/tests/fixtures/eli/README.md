# Odpowiedzi ELI do testów

Pliki w tym katalogu są **syntetyczne**: mają kształt odpowiedzi ELI API Kancelarii Sejmu
(`/eli/acts/{wydawca}/{rok}/{pozycja}` i `/text.html`) opisany w dokumentacji, ale nie zostały
pobrane z produkcyjnego API — środowisko, w którym powstał prototyp, nie miało do niego dostępu.

Służą do testów zachowania synchronizacji (idempotencja, wykrywanie zmian, awarie). Zanim
synchronizacja trafi na produkcję, trzeba:

1. nagrać prawdziwe odpowiedzi dla dwóch aktów testowych wskazanych przez prawnika:
   `uv run python -m app.cli eli-record DU/1994/414 DU/2026/524 --out tests/fixtures/eli/recorded`,
2. dodać test kontraktu na nagraniach (nazwy pól, klucze `references`, format HTML),
3. poprawić `app/modules/eli/schemas.py` (`REFERENCE_ROLES`) i parser, jeśli kontrakt się różni.

Teksty przepisów w plikach HTML są danymi testowymi, nie źródłem prawa.
