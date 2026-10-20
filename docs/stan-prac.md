# Stan prac i decyzje otwarte (20.10.2026)

Plan aplikacji po audycie z 18.10.2026 mówi: „gotowy warunkowo do ograniczonego prototypu integracji z ELI;
niegotowy do pełnej implementacji”. To repozytorium jest takim prototypem — kompletnym technicznie, ale
z treściami, które przed publicznym startem musi przejrzeć prawnik.

## Co jest zrobione i sprawdzone

- Backend z modułami z planu, migracja Alembic zgodna z modelem (`alembic check`), 84 testy pytest.
- Frontend PWA w identyfikacji „Przepisy budowlane”, 26 testów E2E (Playwright) na telefonie (375 px)
  i komputerze, w tym audyt axe WCAG 2.1 AA w motywie jasnym i ciemnym, zwiększone odstępy w tekście
  (WCAG 1.4.12) i pola dotyku 44 px w trybie prostym.
- Obrazy Dockera backendu i frontendu zbudowane i uruchomione; testy E2E przeszły także na nich.
- Zachowanie offline: bez sieci aplikacja nie pokazuje zapamiętanego tekstu prawa (sprawdzone ręcznie
  przez zatrzymanie serwera — emulacja offline w Playwright nie obejmuje żądań service workera).

## Czego nie sprawdzono i dlaczego

- **ELI API na żywo.** Środowisko, w którym powstał prototyp, nie miało dostępu do `api.sejm.gov.pl`.
  Adapter i synchronizacja są przetestowane na syntetycznych odpowiedziach w kształcie z dokumentacji
  (`backend/tests/fixtures/eli/`). Przed produkcją: nagrać odpowiedzi poleceniem `cli eli-record`,
  dodać test kontraktu, potwierdzić nazwy kluczy powiązań (`REFERENCE_ROLES`), pole `legalStatusDate`
  i układ HTML tekstu.
- **Polski słownik Ispell/Hunspell w PostgreSQL.** Zamiast niego działa lekki stemmer w Pythonie
  (te same tematy w indeksie i zapytaniu). Trafność trzeba zmierzyć w prototypie, jak zaleca plan.

## Treści startowe

| Treść | Źródło | Status w aplikacji |
|---|---|---|
| WT § 12 ust. 1 (odległość od granicy) | identyfikacja, brzmienie sprawdzone ze źródłem 19.10.2026 | Własna kompilacja, „Utracił moc 20.09.2026 · stosowany przejściowo” (do 72 h od weryfikacji; potem „Nie potwierdzono”) |
| Prawo budowlane art. 28 ust. 1, art. 29 ust. 1 pkt 1 i 1a | wpisane ręcznie, **nieporównane z Dz.U.** | Typ nierozpoznany, „Nie potwierdzono aktualności” — do zastąpienia tekstem z ELI |
| Objaśnienia, słowniczek (15 haseł), 3 ścieżki, kreator | napisane w prototypie | Opublikowane przez konta demonstracyjne, oznaczone „Treść demonstracyjna — nie przeszła recenzji prawnej” |
| Przepisy przejściowe planowania (studia, warunki zabudowy) | plan aplikacji (MRiT, interpelacja nr 19042, 5.09.2026) | Ścieżka „Kupuję działkę” — demonstracyjna |

Kreator obejmuje tylko wolno stojący dom jednorodzinny; dla garaży, wiat, altan i ogrodzeń mówi wprost,
że tego przypadku jeszcze nie obejmuje — ich podstawy prawne wymagają weryfikacji przez prawnika.

## Poza MVP (zgodnie z planem — nie budowane)

Stan prawny na dowolny dzień i porównanie brzmień, alerty e-mail, konta i logowanie OIDC, praca zespołowa
urzędów, wyjaśnienia GUNB i orzeczenia NSA, planowane zmiany z RCL i Sejmu, asystent AI. Model danych
(dwie osie czasu, historia dopisywana, wersjonowane drzewka) jest przygotowany pod „stan na dzień”.

## Decyzje otwarte z etapu 0 (bez zmian)

- Właściciel produktu i operator usługi; model odpowiedzialności.
- Co dokładnie znaczy „aktualny tekst” w MVP — obecnie: potwierdzenie z synchronizacji lub weryfikacji
  w progu 72 h (`PB_FRESHNESS_THRESHOLD_HOURS`) i brak późniejszych obowiązujących nowelizacji.
- Ostateczny manifest aktów i 10–15 scenariuszy MVP; dwa akty testowe do prototypu ELI.
- Kto pisze treści, kto je niezależnie zatwierdza; testy stanu prawnego do akceptacji przez prawnika
  (`backend/tests/test_freshness.py`).
- Prawa do ponownego wykorzystania źródeł innych niż akty prawne.
- Dostawca logowania (OIDC) zamiast tymczasowych tokenów redakcji.
- Hosting w UE, RPO/RTO, kopie zapasowe i retencja (archiwum źródeł wskazuje `PB_ARCHIVE_DIR`).
- SLA aktualizacji i naprawy błędów (obecnie termin zgłoszenia: 5 dni roboczych).
- Nazwa produktu („Przepisy budowlane” to nazwa robocza; logotyp do wymiany po sprawdzeniu w UPRP).
