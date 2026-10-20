import type { Metadata } from "next";

import { StatusBadge, TextTypeBadge } from "@/components/ds/Badges";
import { api } from "@/lib/api";
import { typo } from "@/lib/format";
import type { FreshnessStatus, TextType } from "@/lib/types";

export const metadata: Metadata = { title: "O serwisie" };

const TYPES: [TextType, string][] = [
  ["ogloszony", "Brzmienie z dnia publikacji w Dzienniku Ustaw. Pokazujemy je z listą późniejszych zmian."],
  ["jednolity", "Obwieszczenie z deklarowanym stanem prawnym. Pokazujemy datę tego stanu i nowelizacje ogłoszone później."],
  ["kompilacja", "Tekst złożony przez redakcję z nowelizacji. Nieurzędowy — przy cytowaniu w decyzji sięgnij do tekstu ogłoszonego."],
  ["nierozpoznany", "Nie da się wiarygodnie ustalić, czym jest tekst. Nigdy nie nazywamy go aktualnym."],
];

const STATUSES: [FreshnessStatus, string, string | null, string | null][] = [
  ["potwierdzona", "Synchronizacja z ELI albo redakcja potwierdziła tekst w ostatnich godzinach; podajemy datę i zakres potwierdzenia.", "2026-10-20", null],
  ["zmiana", "Nowelizacja jest ogłoszona, ale jeszcze nie obowiązuje. Pokazujemy tekst obowiązujący dziś i datę zmiany.", null, "2027-01-01"],
  ["przejsciowa", "Akt utracił moc, ale przepis przejściowy pozwala go jeszcze stosować — na podanych warunkach.", "2026-09-20", null],
  ["niepotwierdzona", "Nie potwierdziliśmy aktualności: synchronizacja się spóźnia, tekst ma nierozpoznany typ albo obowiązuje późniejsza nowelizacja.", null, null],
  ["zawieszona", "Przepisu nie stosuje się w okresie zawieszenia. Najsilniejszy sygnał w serwisie.", null, null],
];

export default async function Page() {
  const synonyms = await api.synonyms();
  return (
    <div className="pb-stack-5" style={{ maxWidth: 820 }}>
      <div className="pb-page-head" style={{ marginBottom: 0 }}>
        <h1 className="ui-display">O serwisie</h1>
        <p className="ui-body">
          {typo(
            "Przepisy budowlane w jednym miejscu: oficjalny tekst, data, na którą jest aktualny, i objaśnienie prostym językiem. Dla inwestorów i dla pracowników organów administracji architektoniczno-budowlanej i nadzoru budowlanego.",
          )}
        </p>
      </div>

      <section className="pb-panel" aria-labelledby="zasady">
        <h2 id="zasady" className="ui-heading">
          Zasady
        </h2>
        <ul className="ui-body pb-measure" style={{ paddingLeft: "var(--space-5)" }}>
          <li>{typo("Źródło oficjalne zawsze pierwsze. Każdy przepis prowadzi do aktu w Dzienniku Ustaw; nie udajemy źródła prawa.")}</li>
          <li>{typo("Każdy tekst ma jawny typ i datę. Słowo „aktualny” pada tylko z podstawą i zakresem potwierdzenia.")}</li>
          <li>{typo("Dwie warstwy treści: tekst przepisu bez zmian i objaśnienie prostym językiem, wyraźnie oznaczone jako nieurzędowe.")}</li>
          <li>{typo("Maszyna wykrywa, człowiek zatwierdza. Zmiany w prawie wyłapuje synchronizacja, objaśnienia publikuje dopiero niezależny recenzent.")}</li>
          <li>{typo("Awaria nie udaje świeżości. Gdy nie da się potwierdzić aktualności źródła, mówimy to wprost.")}</li>
        </ul>
      </section>

      <section className="pb-panel" aria-labelledby="typy">
        <h2 id="typy" className="ui-heading">
          Typy tekstu
        </h2>
        <dl className="pb-stack-4">
          {TYPES.map(([t, desc]) => (
            <div key={t} className="pb-stack-2">
              <dt>
                <TextTypeBadge type={t} />
              </dt>
              <dd className="ui-body" style={{ margin: 0 }}>
                {typo(desc)}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="pb-panel" aria-labelledby="statusy">
        <h2 id="statusy" className="ui-heading">
          Statusy aktualności — od spokojnego do alarmowego
        </h2>
        <dl className="pb-stack-4">
          {STATUSES.map(([s, desc, date, eff]) => (
            <div key={s} className="pb-stack-2">
              <dt>
                <StatusBadge status={s} date={date} effectiveDate={eff} />
              </dt>
              <dd className="ui-body" style={{ margin: 0 }}>
                {typo(desc)}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="pb-panel" aria-labelledby="porada">
        <h2 id="porada" className="ui-heading">
          Informacja, nie porada prawna
        </h2>
        <p className="ui-body pb-measure">
          {typo(
            "Objaśnienia pisze i podpisuje człowiek, a zatwierdza niezależny recenzent. Nie odpowiadamy na pytania o konkretną działkę, decyzję czy spór — z nimi zwróć się do urzędu albo prawnika. Serwis nie zastępuje wypisu i wyrysu z planu miejscowego ani informacji z gminy.",
          )}
        </p>
        <p className="ui-body pb-measure" style={{ marginTop: "var(--space-2)" }}>
          {typo(
            "Serwis jest niezależny i nie jest serwisem państwowym. Operator usługi i model odpowiedzialności zostaną wskazane przed publicznym startem.",
          )}
        </p>
      </section>

      <section className="pb-panel" aria-labelledby="dane">
        <h2 id="dane" className="ui-heading">
          Dane i prywatność
        </h2>
        <p className="ui-body pb-measure">
          {typo(
            "Z serwisu korzystasz bez konta. Zapisujemy tylko wybór trybu (ciasteczko funkcjonalne) i — w Twojej przeglądarce — odpowiedzi w kreatorze. Adres e-mail w zgłoszeniu błędu jest opcjonalny; usuwamy go po zamknięciu zgłoszenia.",
          )}
        </p>
      </section>

      <section className="pb-panel" aria-labelledby="dostepnosc">
        <h2 id="dostepnosc" className="ui-heading">
          Dostępność
        </h2>
        <p className="ui-body pb-measure">
          {typo(
            "Celem jest zgodność z WCAG 2.1 na poziomie AA: obsługa klawiaturą i czytnikiem ekranu, kontrast, czytelność na telefonie. Kolor nigdy nie jest jedynym nośnikiem informacji — statusy różnią się też ikoną, etykietą i obrysem.",
          )}
        </p>
      </section>

      <section className="pb-panel" aria-labelledby="synonimy-h" id="synonimy">
        <h2 id="synonimy-h" className="ui-heading">
          Słownik synonimów wyszukiwarki
        </h2>
        <p className="ui-body pb-measure" style={{ marginBottom: "var(--space-3)" }}>
          {typo("Gdy wpiszesz słowo z lewej kolumny, szukamy też terminów z prawej. Słownik jest jawny, żeby było wiadomo, skąd wynik.")}
        </p>
        <div className="pb-table-wrap">
          <table className="pb-table ui-small" aria-labelledby="synonimy-h">
            <thead>
              <tr>
                <th scope="col">Wpisujesz</th>
                <th scope="col">Szukamy też</th>
                <th scope="col">Uwagi</th>
              </tr>
            </thead>
            <tbody>
              {synonyms.map((s) => (
                <tr key={s.term}>
                  <td>{s.term}</td>
                  <td>{s.expansions.join(", ")}</td>
                  <td className="pb-muted">{s.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
