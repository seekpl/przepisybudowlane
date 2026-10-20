Identyfikacja aplikacji „Przepisy budowlane w jednym miejscu” — ma budzić zaufanie jak dokument urzędowy, a czytać się jak dobra instrukcja. Jej pierwsze zadanie: jednoznacznie pokazać, **czy tekst przepisu jest urzędowy** i **czy jego aktualność jest potwierdzona**. Każdą decyzję projektową sprawdzaj pytaniem: czy to pomaga uwierzyć w źródło i szybciej zrozumieć przepis?

„Przepisy budowlane” to nazwa robocza. Znak — „paragraf wymiarowany” (grupa **Logo**) — od nazwy nie zależy; logotyp obok niego wymień, gdy nazwa przejdzie sprawdzenie w UPRP i dostępności domeny .pl.

## Osobowość: pewna, jasna, spokojna

| Jest | Nie jest |
|---|---|
| Wiarygodna jak dokument | Urzędowo sztywna i nieprzystępna |
| Spokojna i rzeczowa | Alarmistyczna („UWAGA! KARY!”) |
| Przystępna i ludzka | Infantylna, „startupowa”, żartobliwa |
| Precyzyjna i oszczędna | Ozdobna, z dekoracjami bez funkcji |
| Niezależna i jawna co do źródeł | Udająca serwis państwowy |

Nie używaj godła, barw biało-czerwonych jako przewodnich, kolorystyki gov.pl, młotka sędziowskiego, kasku ani cegieł.

## Treść i ton

- Do inwestora mów w drugiej osobie, krótkimi zdaniami: „Ścianę z oknami odsuń od granicy co najmniej o 4 m.” Do urzędnika — rzeczowo, bez skrótów myślowych.
- Ostrzeżenia mówią, co się dzieje i co zrobić: „Nie potwierdziliśmy, że ten tekst jest aktualny. Zanim się na nim oprzesz, porównaj go z oficjalnym tekstem.” Bez wykrzykników, bez wersalików, bez straszenia karami.
- Wielka litera tylko na początku etykiety („Tekst jednolity”, nie „Tekst Jednolity” ani „TEKST JEDNOLITY”).
- Jednostki redakcyjne zawsze w formie urzędowej: „art.”, „§”, „ust.”, „pkt”, „lit.”, ze spacją niełamiącą po skrócie i przed liczbą. Publikator: „Dz.U. 2022 poz. 1225”.
- Daty: `d.mm.rrrr` w odznakach i metryce („18.10.2026”), słownie w zdaniach („1 stycznia 2027 r.”). Liczby z przecinkiem dziesiętnym i spacją przed jednostką („1,5 m”).
- Cudzysłowy polskie „ ”. Półpauza – w przedziałach, pauza — w zdaniach.
- Objaśnienie nigdy nie udaje przepisu: zawsze z etykietą „Objaśnienie nieurzędowe”, zawsze w `Explanation`. Gdy coś może zmienić odpowiedź (plan miejscowy, warunki zabudowy), napisz to wprost.
- Bez emoji.

## Kolor

Kolor niesie znaczenie, nie dekorację. Każda rola istnieje w motywie jasnym i ciemnym.

- **Tła:** strona `surface` (lekko ciepły papier), karty `surface-raised`, wgłębienia (metryka w trybie prostym, podstawa prawna wyniku) `surface-sunken`.
- **Tekst:** `ink` na wszystkich tłach; tekst pomocniczy `ink-muted` — też co najmniej 4,5:1. Linie bez znaczenia `line`; obrysy kontrolek `line-strong`.
- **Marka:** `primary` — przyciski główne, linki, bieżący krok, budynek na rysunkach. Tekst na wypełnieniu `primary` zawsze w `on-primary`. Zaznaczenie: `primary-soft` z tekstem `primary-soft-ink`.
- **Akcent:** `accent` (ochra z rysunku technicznego) tylko dla linii wymiarowych i rzadkich wyróżnień graficznych. Nigdy dla statusów, nigdy jako kolor tekstu.
- **Statusy aktualności**, od spokojnego do alarmowego: potwierdzona (`status-ok`) → zmiana w drodze (`status-pending`) → utracił moc, stosowany przejściowo (`status-critical`, obrys 2 px przerywany) → nie potwierdzono (`status-critical`, obrys 2 px ciągły) → treść zawieszona (`status-critical-solid` z `on-status-critical`). Pełne wypełnienie ma tylko „Treść zawieszona” — najsilniejszy sygnał w systemie.
- **Objaśnienia:** `explain-bg` z obrysem `explain-line` i etykietą w `explain-ink`. Chłodne, spokojne, nie kojarzy się z błędem.
- **Typ nierozpoznany:** `type-unknown` na `type-unknown-bg` z przerywanym obrysem `type-unknown-line`.
- **Fokus:** `focus-ring`, linia `focus-width` (2 px) z takim samym odstępem — widoczny na każdej powierzchni.

Kontrast policzony dla obu motywów (WCAG 2.1 AA: tekst 4,5:1, elementy interfejsu i grafiki 3:1):

| Para | Jasny | Ciemny | Próg |
|---|---|---|---|
| `ink` na `surface-raised` | 15,5:1 | 13,3:1 | 4,5:1 |
| `ink-muted` na `surface-sunken` | 5,7:1 | 8,5:1 | 4,5:1 |
| `primary` na `surface-raised` | 11,2:1 | 8,6:1 | 4,5:1 |
| `on-primary` na `primary` | 11,5:1 | 9,1:1 | 4,5:1 |
| `status-ok` na `status-ok-bg` | 5,5:1 | 7,5:1 | 4,5:1 |
| `status-pending` na `status-pending-bg` | 6,1:1 | 7,8:1 | 4,5:1 |
| `status-critical` na `status-critical-bg` | 6,5:1 | 7,7:1 | 4,5:1 |
| `on-status-critical` na `status-critical-solid` | 7,7:1 | 8,7:1 | 4,5:1 |
| `explain-ink` na `explain-bg` | 8,5:1 | 8,8:1 | 4,5:1 |
| `type-unknown` na `type-unknown-bg` | 7,4:1 | 9,6:1 | 4,5:1 |
| `line-strong` na `surface-raised` | 3,7:1 | 3,8:1 | 3:1 |
| `focus-ring` na `surface-sunken` | 9,4:1 | 9,9:1 | 3:1 |
| `accent` na `surface-raised` | 3,5:1 | 7,6:1 | 3:1 |

## Typografia

Krój szeryfowy oznacza „to jest dokument”, bezszeryfowy — „to wyjaśniamy my”. Nigdy ich nie zamieniaj.

- **Tekst prawa:** PB Serif (`--font-serif`, na bazie Source Serif 4). `law-simple` (18/28) na telefonie, `law-expert` (17/26) na komputerze; jednostka redakcyjna w `law-unit`. Wiersz do `measure-law` (75ch, ok. 80 znaków tekstu).
- **Interfejs i objaśnienia:** PB Sans (`--font-sans`, na bazie Source Sans 3). Skala: `ui-display` 28/34, `ui-title` 22/28, `ui-heading` 18/24, `ui-body` 16/24, `ui-small` 14/21, `ui-label` 13/16. Tekst podstawowy na telefonie nigdy mniejszy niż `ui-body` (16 px); `ui-small` tylko w trybie eksperckim i dla podpisów. Wiersz objaśnień do `measure-text`.
- **Metryka i identyfikatory:** PB Mono (`--font-mono`, na bazie Source Code Pro) w `meta` / `meta-small` — publikator, ELI, daty; zero z kropką, „l” z ogonkiem.
- Wybór po teście na art. 29 Prawa budowlanego (grupa **Kroje**): w IBM Plex Sans „I” i „l” różnią się niemal tylko wysokością, w Source Sans 3 „l” ma ogonek — 1, l i I są wyraźnie różne we wszystkich trzech krojach.
- Cyfry są tabelaryczne domyślnie — kolumny metryki wyrównują się same. Trzy grubości w całej aplikacji: 400, 500, 600.
- Fonty są hostowane samodzielnie i przycięte do łaciny z polskimi znakami (razem ok. 190 KB, SIL OFL 1.1, tekst licencji w `fonts/OFL.txt`). Przycięty font to wersja zmodyfikowana, a nazwa „Source” jest w licencji zastrzeżona — stąd nazwy PB Sans, PB Serif i PB Mono. Nie ładuj fontów z Google Fonts.
- W treściach (objaśnienia, komunikaty) stawiaj spację niełamiącą po jednoliterowych wyrazach („w”, „o”, „z”), po skrótach („art.”, „ust.”, „§”) i między liczbą a jednostką („4 m”). Tekstu prawa nie zmieniaj.
- Układ musi wytrzymać zwiększone odstępy w tekście (WCAG 1.4.12): nie ustawiaj stałych wysokości bloków tekstu.

## Dwa tryby, jedna marka

Tryb prosty (inwestor, telefon, krótkie sesje, często stres) i ekspercki (urzędnik, komputer, długa praca) używają tych samych kolorów, ikon i etykiet. Różnią się tylko gęstością:

| | Prosty | Ekspercki |
|---|---|---|
| Pole dotyku / kontrolka | `control-simple` 44 px | `control-expert` 32 px |
| Tekst prawa | `law-simple` | `law-expert` |
| Padding karty | `space-4` | `space-4` |
| Odstęp sekcji | `space-5` | `space-4` |
| Kolejność w karcie | komunikat → objaśnienie → oficjalne brzmienie → metryka | komunikat → metryka → tekst → objaśnienie |

W obu trybach komunikat o aktualności stoi **przed** tekstem przepisu.

## Odstępy, zaokrąglenia, cienie

- Odstępy między blokami i padding kart: wielokrotności 8 px; 4 px tylko dla mikroodstępów (ikona–etykieta). Skala: `space-1` 4, `space-2` 8, `space-3` 12, `space-4` 16, `space-5` 24, `space-6` 32, `space-7` 48.
- Zaokrąglenia małe, jak w dokumencie: `radius-sm` (2 px) odznaki, `radius-md` (4 px) przyciski i komunikaty, `radius-lg` (8 px) karty.
- Bez cieni i gradientów — powierzchnie oddzielają obrysy `line` i różnica tła.
- Ruch: brak. Stany najechania zmieniają się natychmiast; jeśli kiedyś dojdzie animacja, wolno animować tylko `opacity` i `transform` (100–300 ms), a przy `prefers-reduced-motion` — nic.

## Ikonografia

- Jeden zestaw: Lucide 0.460.0 (licencja ISC), linia 2 px na siatce 24 px, kolor z `currentColor`. Ikony są wpięte w komponent `Icon`; nowe bierz tylko z tego zestawu.
- Ikona zawsze stoi obok etykiety. Typy i statusy różnią się kształtem obrysu, nie tylko kolorem: `circle-check`, `calendar-clock`, `hourglass`, `triangle-alert`, `octagon-pause`; `file-text`, `book-check`, `file-pen`, `file-question`.
- Objaśnienie oznacza `message-square-text`, wynik kreatora `scale`, oficjalne źródło `external-link`.

## Znak i logo

- Znak „paragraf wymiarowany”: § z PB Serif na płytce `primary`, pod nim linia wymiarowa w `accent`. Wersje, pole ochronne (¼ wysokości znaku), minimalne rozmiary i błędne użycia — w grupie **Logo**; favicony, ikony PWA, manifest i obraz do udostępniania — w grupie **Ikony**.
- W interfejsie logo stoi w nagłówku w wersji poziomej (telefon: sam znak + nazwa w `ui-heading`). Znaku nie używaj jako ikony statusu ani ozdobnika w treści.

## Ilustracje

- Tylko rysunki techniczne z grupy **Rysunki**: rzut działki, przekrój, linie wymiarowe. Budynek w `primary` (2,5 px), granice i teren w `ink-muted` (1,5 px, granica punkt-kreska), wymiary w `accent` (1,5 px). Czytelne w czerni i bieli.
- Każdy rysunek ma opis tekstowy i stoi przy objaśnieniu, nigdy zamiast tekstu przepisu.
- Bez zdjęć stockowych i ilustracji z postaciami.

## Komponenty

`ProvisionCard` składa się z `StatusBadge`, `TextTypeBadge`, `FreshnessNotice`, `LawText`, `Explanation` i `Citation`; `WizardStep` prowadzi kreator. Karta przepisu to wzorzec strony „szczegóły”, kreator — „formularz wieloetapowy”.

Podglądy pokazują prawdziwy stan prawny sprawdzony 19.10.2026 (najnowsze znalezione źródła z 6.10.2026): § 12 ust. 1 warunków technicznych w brzmieniu z Dz.U. 2023 poz. 2442 (tekst jednolity z 2022 r. tej zmiany nie zawiera, stąd „Własna kompilacja”); rozporządzenie utraciło moc 20.09.2026 i jest stosowane przejściowo na podstawie art. 102a Prawa budowlanego. Wynik kreatora opiera się na art. 29 ust. 1 pkt 1a (t.j. Dz.U. 2026 poz. 524); nowelizacji ogłoszonych po tym tekście jednolitym nie sprawdzono, więc ma status „Nie potwierdzono”.
