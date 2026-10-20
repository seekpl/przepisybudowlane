# Profil UX

Ustawienia, według których umiejętności UX (VectorLab) i audyty oceniają tę identyfikację i aplikację. Każda zmiana profilu zmienia wynik audytu — zmieniaj go świadomie, nie pod konkretny ekran.

## A. Wzorzec estetyczny

**Notion**: ciepłe, papierowe tło, typografia jak w dobrze złożonym dokumencie, mało obramowań, brak dekoracji bez funkcji. Tryb ekspercki jest gęstszy (mniejsze kontrolki i odstępy), ale korzysta z tych samych tokenów, kolorów i ikon — to jedna marka w dwóch gęstościach.

## B. Zakazy

- Domyślna lista zakazów umiejętności anti-slop: tęczowe gradienty na przyciskach, rozmycia (glassmorphism), ilustracje z postaciami w pustych stanach, ozdobne ikony w polach, „pigułki” wokół zwykłych metadanych.
- Z briefu: godło i wszystko, co sugeruje serwis państwowy; biel i czerwień jako barwy przewodnie; kolorystyka gov.pl; młotek sędziowski; kask i cegły; alarmistyczny ton („UWAGA! KARY!”), wykrzykniki i wersaliki; zdjęcia stockowe.
- Wyjątek: odznaki typu tekstu i statusu aktualności nie są ozdobnymi „pigułkami” — to wymagany przez brief nośnik znaczenia (etykieta, ikona i kolor razem). Zwykłe metadane (daty, publikator, jednostka) pozostają zwykłym tekstem.

## C. Dostępność

- Cel: **WCAG 2.1 AA**. Tekst 4,5:1, duży tekst, elementy interfejsu i grafiki 3:1; kolor nigdy nie jest jedynym nośnikiem informacji.
- Pola dotyku: **44×44 px w trybie prostym** (telefon), **minimum 32×32 px w trybie eksperckim** (komputer, mysz; WCAG 2.2 wymaga 24×24).
- Fokus zawsze widoczny: obrys `focus-ring` 2 px z odstępem 2 px, w obu motywach.
- Układ wytrzymuje zwiększone odstępy w tekście (WCAG 1.4.12) i szerokość 375 px bez przewijania w poziomie.

## D. Ton komunikatów

**Ciepły i ludzki, spokojny.** Do inwestora w drugiej osobie, krótkimi zdaniami; do urzędnika rzeczowo. Przyciski od czasownika, wielka litera tylko na początku. Komunikaty mówią, co się stało i co zrobić — nigdy nie obwiniają („Wybierz jedną odpowiedź, żeby przejść dalej.”). Bez wykrzykników i emoji.

## E. Ikony

**Lucide 0.460.0** (licencja ISC), linia 2 px na siatce 24 px, osadzone w komponencie `Icon`. Ikona zawsze obok etykiety; nowe ikony tylko z tego zestawu i tej wersji.

## Statusy aktualności

Pięć statusów, od spokojnego do alarmowego: potwierdzona → zmiana w drodze → utracił moc, stosowany przejściowo → nie potwierdzono → treść zawieszona. Piąty status („przejściowy”) rozszerza brief; zaakceptowany przez właściciela produktu.
