# Stan prac i decyzje otwarte (24.10.2026)

Plan aplikacji po audycie z 18.10.2026 mówi: „gotowy warunkowo do ograniczonego prototypu integracji z ELI;
niegotowy do pełnej implementacji”. To repozytorium jest takim prototypem. Od 21.10.2026 prace idą według
arkusza „Automatyzacja prototypu” (26 działań w 5 obszarach); stan każdego działania jest w kolumnie Status.

## Co jest zrobione i sprawdzone

- **ELI API na żywo (obszar 1).** Workflow `eli-nagrania` codziennie nagrywa w GitHub Actions odpowiedzi
  prawdziwego ELI dla aktów z manifestu; testy kontraktu (schemat, zamknięty słownik kluczy powiązań,
  `legalStatusDate` w obowiązującym tekście jednolitym) działają na tych nagraniach. Naruszenie kontraktu
  podnosi alarm źródła, wstrzymuje synchronizację i zmienia status wszystkich kart na „Nie potwierdzono
  aktualności”; wznawia człowiek w panelu redakcji. Gdy nagrania się zmieniają, a testy przechodzą,
  workflow sam otwiera i scala PR; gdy kontrakt pada — otwiera zgłoszenie `alarm-eli`.
- **Tekst prawa tylko z ELI (obszar 2).** Baza nie przyjmie wersji tekstu bez migawki z ELI (ograniczenia
  w schemacie), treści startowe nie zawierają brzmień. Tekst w HTML przechodzi przez parser struktury ELI;
  tekst tylko w PDF (obecne teksty jednolite Prawa budowlanego, k.p.a. i ustawy o planowaniu) — przez
  parser PDF i zawsze do kontroli człowieka. Przyjęcie tekstu w panelu porównuje jednostki z poprzednim
  brzmieniem i zawiesza zależne treści. Dla aktu uchylonego automat czyta tekst jednolity aktu uchylającego
  i podaje kandydatów na przepisy przejściowe; okres stosowania zapisuje recenzent.
- **Treści redakcyjne (obszar 3).** Warstwa automatyczna (tekst, metryka, typ, status, nowelizacje)
  publikuje się bez człowieka. Słowniczek ma dosłowne definicje ustawowe z każdego przyjętego tekstu
  (np. art. 3 Prawa budowlanego, § 3 warunków technicznych). Szkice objaśnień pisze AI (Claude API) wyłącznie z akapitów przepisu z ELI;
  każde zdanie ma cytat, a walidatory bez AI odrzucają zdania, których cytat, liczby, daty lub odesłania
  nie występują w cytowanym tekście. Zmiana brzmienia zawiesza opublikowane objaśnienie i zleca nowy szkic.
  Recenzent widzi tylko różnice (brzmienie po słowach, objaśnienie po zdaniach z cytatami) i zatwierdza
  z nazwiska — szkic nigdy nie publikuje się sam, a karta mówi, że przygotowało go AI.
- **Kreator (obszar 4).** Punkty art. 29 ust. 1 i 2 Prawa budowlanego są odczytywane jako reguły
  (wymóg, obiekt, warunki liczbowe); do kreatora trafia tylko reguła zatwierdzona przez recenzenta dla
  danego brzmienia. Dla przypadków, których kreator nie obejmuje, pokazuje dosłowną listę punktów do
  sprawdzenia (dopasowanie po lematach), a nie odpowiedź.
- **Trafność wyszukiwania (obszar 5).** Zestaw testowy budowany z treści (Morfeusz 2), trzy warianty
  (stemmer, lematyzacja, Hunspell w PostgreSQL) porównane; wygrała lematyzacja (`trafnosc.json`).
  CI blokuje zmianę, która obniża trafność. Zapytania bez wyników trafiają do redakcji jako propozycje
  synonimów — zapisujemy tylko treść zapytania i licznik.
- Testy: 187 testów pytest, 28 testów E2E (Playwright) na telefonie (375 px) i komputerze, w tym audyt axe
  WCAG 2.1 AA w obu motywach, zwiększone odstępy w tekście (WCAG 1.4.12) i pola dotyku 44 px.

## Czego nie sprawdzono i dlaczego

- **Prawdziwe wywołanie Claude API.** Środowisko, w którym powstał kod, nie ma klucza `ANTHROPIC_API_KEY`.
  Testy sprawdzają cały przebieg na atrapie klienta, a kształt żądania i obsługę błędów — na prawdziwym SDK
  z podstawionym transportem HTTP. Pierwszy przebieg z kluczem: `cli szkice-ai`, potem kolejka w panelu.
- **ELI API z tego środowiska.** Środowisko Claude Code nie ma `api.sejm.gov.pl` na liście dozwolonych
  domen, więc nagrania powstają w GitHub Actions. Żeby nagrywać lub synchronizować także tutaj, właściciel
  środowiska dopisuje domenę w ustawieniach środowiska (Network access → Allowed domains) — arkusz, 1.7.
- **Odczyt PDF.** Parser PDF jest sprawdzony na prawdziwych tekstach jednolitych, ale każdy tekst z PDF
  czeka na porównanie z oryginałem przez człowieka, zanim cokolwiek pokaże.

## Treści startowe

| Treść | Źródło | Status w aplikacji |
|---|---|---|
| Warunki techniczne (Dz.U. 2002 poz. 690), tekst jednolity Dz.U. 2022 poz. 1225 | ELI, HTML | Tekst przyjęty automatycznie; według ELI akt uznany za uchylony z dniem 21.09.2026 — okres stosowania przejściowego zapisuje recenzent (kandydaci z aktu uchylającego, m.in. art. 66) |
| Prawo budowlane, k.p.a., ustawa o planowaniu — obecne teksty jednolite | ELI, tylko PDF | Do kontroli człowieka; do tego czasu karta pokazuje metrykę i link do oficjalnego tekstu, bez brzmienia |
| Objaśnienia, słowniczek „prostym językiem”, 3 ścieżki, kreator | napisane w prototypie | Publikowane przez konta demonstracyjne tylko razem z tekstem z ELI, oznaczone „Treść demonstracyjna — nie przeszła recenzji prawnej” |
| Definicje ustawowe w słowniczku | parser, dosłowny cytat | Publikowane automatycznie z przyjętego tekstu |

Kreator obejmuje wolno stojący dom jednorodzinny; dla garaży, wiat, altan i ogrodzeń mówi wprost, że
tego przypadku jeszcze nie obejmuje, i pokazuje przepisy do sprawdzenia.

## Model odpowiedzialności — do decyzji operatora (arkusz, 3.7 i 3.8)

Kod realizuje wariant **„warstwa z przeglądem”**: AI pisze tylko szkice z tekstu z ELI, każde zdanie ma
sprawdzony cytat, a publikuje wskazany z nazwiska recenzent, który może być zewnętrzny (np. kancelaria).
Karta mówi, że szkic przygotowało AI, i podaje, kto go zweryfikował.

Wariant **„pełna automatyzacja”** (publikacja szkicu bez człowieka) nie jest zbudowany. Zanim operator
wybierze wariant, potrzebna jest opinia prawnika (3.7), czy objaśnienia prawa budowlanego to „sprawy
interesu publicznego” w rozumieniu art. 50 ust. 4 AI Act. Ten przepis zwalnia z obowiązku ujawniania tekstu
wygenerowanego przez AI treści, które przeszły przegląd człowieka lub kontrolę redakcyjną, gdy ktoś ponosi
odpowiedzialność redakcyjną za publikację — czyli wariant obecny.

Decyzja operatora: _(do wpisania)_.

## Poza MVP (zgodnie z planem — nie budowane)

Stan prawny na dowolny dzień i porównanie brzmień dla czytelnika, alerty e-mail, konta i logowanie OIDC,
praca zespołowa urzędów, wyjaśnienia GUNB i orzeczenia NSA, planowane zmiany z RCL i Sejmu, asystent AI
dla czytelnika. Model danych (dwie osie czasu, historia dopisywana, wersjonowane drzewka) jest przygotowany
pod „stan na dzień”.

## Decyzje otwarte z etapu 0

- Właściciel produktu i operator usługi; model odpowiedzialności (wyżej).
- Co dokładnie znaczy „aktualny tekst” w MVP — obecnie: potwierdzenie z synchronizacji lub weryfikacji
  w progu 72 h (`PB_FRESHNESS_THRESHOLD_HOURS`) i brak późniejszych obowiązujących nowelizacji.
- Ostateczny manifest aktów i 10–15 scenariuszy MVP.
- Kto pisze treści i kto je niezależnie zatwierdza; testy stanu prawnego do akceptacji przez prawnika
  (`backend/tests/test_freshness.py`).
- Prawa do ponownego wykorzystania źródeł innych niż akty prawne.
- Dostawca logowania (OIDC) zamiast tymczasowych tokenów redakcji.
- Hosting w UE, RPO/RTO, kopie zapasowe i retencja (archiwum źródeł wskazuje `PB_ARCHIVE_DIR`).
- SLA aktualizacji i naprawy błędów (obecnie termin zgłoszenia: 5 dni roboczych).
- Nazwa produktu („Przepisy budowlane” to nazwa robocza; logotyp do wymiany po sprawdzeniu w UPRP).
