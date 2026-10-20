import type { Metadata } from "next";
import Link from "next/link";

import { StatusBadge, TextTypeBadge } from "@/components/ds/Badges";
import { api } from "@/lib/api";
import { dateTime, typo } from "@/lib/format";

export const metadata: Metadata = { title: "Stan danych" };

const RUN_STATUS: Record<string, string> = { sukces: "udana", czesciowy: "częściowa", blad: "nieudana", w_toku: "w toku" };
const TASKS: Record<string, string> = {
  nowelizacja: "Nowelizacje do opisania",
  zmiana_tekstu: "Zmienione przepisy do sprawdzenia",
  kontrola_parsera: "Teksty do kontroli człowieka",
  awaria_synchronizacji: "Awarie synchronizacji",
  zgloszenie_bledu: "Zgłoszenia błędów",
};

export default async function Page() {
  const st = await api.status();
  const tasks = Object.entries(st.open_tasks);
  return (
    <>
      <div className="pb-page-head">
        <h1 className="ui-display">Stan danych</h1>
        <p className="ui-body">
          {typo(
            `Pokazujemy, kiedy ostatnio udało się pobrać dane z ELI API Kancelarii Sejmu. Jeśli od udanej synchronizacji minie więcej niż ${st.threshold_hours} godzin, karty przepisów mówią wprost, że nie potwierdziliśmy aktualności.`,
          )}
        </p>
      </div>
      <section className="pb-panel" aria-labelledby="sync">
        <h2 id="sync" className="ui-heading">
          Synchronizacja z ELI
        </h2>
        {st.last_success_at ? (
          <p className="ui-body">
            Ostatnia udana: <span className="meta">{dateTime(st.last_success_at)}</span>
          </p>
        ) : (
          <p className="ui-body pb-measure">
            {typo(
              "Synchronizacja z ELI nie była jeszcze uruchomiona w tym środowisku. Dopóki nie ruszy, przepisy mają status „Nie potwierdzono aktualności”, chyba że redakcja sprawdziła je ręcznie.",
            )}
          </p>
        )}
      </section>

      <section className="pb-section" aria-labelledby="akty">
        <h2 id="akty" className="ui-title">
          Akty
        </h2>
        <div className="pb-table-wrap">
          <table className="pb-table ui-small">
            <thead>
              <tr>
                <th scope="col">Akt</th>
                <th scope="col">Tekst</th>
                <th scope="col">Aktualność</th>
                <th scope="col">Wiek danych</th>
              </tr>
            </thead>
            <tbody>
              {st.acts.map((a) => (
                <tr key={a.slug}>
                  <td>
                    <Link href={`/akty/${a.slug}`}>{a.short_title}</Link>
                  </td>
                  <td>
                    {a.text_type ? <TextTypeBadge type={a.text_type} /> : "brak"}
                    {a.journal ? <div className="meta-small">{a.journal}</div> : null}
                  </td>
                  <td>
                    <StatusBadge status={a.freshness} />
                  </td>
                  <td className="meta-small">
                    {a.data_age_hours === null ? "brak synchronizacji" : `${a.data_age_hours.toLocaleString("pl-PL")} h`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="pb-section" aria-labelledby="zadania">
        <h2 id="zadania" className="ui-title">
          Zaległe zadania redakcji
        </h2>
        {tasks.length === 0 ? (
          <p className="ui-body">Brak otwartych zadań.</p>
        ) : (
          <ul className="pb-plain-list ui-body">
            {tasks.map(([k, n]) => (
              <li key={k}>
                {TASKS[k] ?? k}: <span className="meta">{n}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="pb-section" aria-labelledby="przebiegi">
        <h2 id="przebiegi" className="ui-title">
          Ostatnie przebiegi
        </h2>
        {st.runs.length === 0 ? (
          <p className="ui-body pb-muted">Jeszcze żadnego.</p>
        ) : (
          <div className="pb-table-wrap">
            <table className="pb-table ui-small">
              <thead>
                <tr>
                  <th scope="col">Start</th>
                  <th scope="col">Wynik</th>
                  <th scope="col">Szczegóły</th>
                </tr>
              </thead>
              <tbody>
                {st.runs.map((r) => (
                  <tr key={r.id}>
                    <td className="meta-small">{dateTime(r.started_at)}</td>
                    <td>{RUN_STATUS[r.status] ?? r.status}</td>
                    <td>
                      {r.errors.length > 0
                        ? r.errors.map((e, i) => <div key={i}>{Object.values(e).join(": ")}</div>)
                        : `Nowe wersje tekstu: ${r.stats.nowe_wersje_tekstu ?? 0}, nowelizacje: ${r.stats.nowe_nowelizacje ?? 0}`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
