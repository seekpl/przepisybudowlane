import type { Metadata } from "next";

import { editorLogout } from "@/app/actions";
import { CloseAlarmForm, CloseTaskForm, LoginForm, TextDecisionForm, TransitionalForm, TransitionForm } from "@/components/editorial/Forms";
import { Icon } from "@/components/ds/Icon";
import { editorialFetch } from "@/lib/api";
import { editorToken } from "@/lib/editor";
import { dateTime, shortDate } from "@/lib/format";

export const metadata: Metadata = { title: "Redakcja", robots: { index: false } };

interface Me {
  name: string;
  roles: string[];
}
interface Candidate {
  klucz: string;
  jednostka: string;
  tekst: string;
}
interface Task {
  id: number;
  kind: string;
  title: string;
  due_on: string | null;
  created_at: string;
  act: string | null;
  act_slug: string | null;
  details: {
    akt_uchylajacy?: string;
    publikator?: string;
    od?: string | null;
    kandydaci?: Candidate[];
    blad?: string;
  };
}
interface Content {
  entity: string;
  id: number;
  label: string;
  version_no: number;
  state: string;
  author: string;
  reviewer: string | null;
  is_demo: boolean;
}
interface TextReview {
  id: number;
  akt: string;
  publikator: string;
  jakosc: number | null;
  uwagi: string | null;
}
interface Alarm {
  id: number;
  source: string;
  kind: string;
  title: string;
  details: { adres?: string; naruszenia?: { kod: string; opis: string }[] };
  raised_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution: string | null;
}
interface Report {
  number: string;
  target_label: string | null;
  target_path: string;
  message: string;
  state: string;
  due_on: string;
  has_email: boolean;
}

const STATE: Record<string, string> = {
  szkic: "Szkic",
  recenzja: "Recenzja",
  zatwierdzony: "Zatwierdzony",
  opublikowany: "Opublikowany",
  zawieszony: "Zawieszony",
  cofniety: "Cofnięty",
};

export default async function Page() {
  const token = await editorToken();
  let me: Me | null = null;
  if (token) {
    try {
      me = await editorialFetch<Me>(token, "/ja");
    } catch {
      me = null;
    }
  }
  if (!token || !me) {
    return (
      <div className="pb-stack-5">
        <div className="pb-page-head" style={{ marginBottom: 0 }}>
          <h1 className="ui-display">Panel redakcji</h1>
          <p className="ui-body">Zadania po wykrytych zmianach, recenzje i publikacja objaśnień, kontrola tekstów i zgłoszenia.</p>
        </div>
        <LoginForm />
      </div>
    );
  }
  const [tasks, contents, texts, reports, alarms] = await Promise.all([
    editorialFetch<Task[]>(token, "/zadania"),
    editorialFetch<Content[]>(token, "/tresci"),
    editorialFetch<TextReview[]>(token, "/teksty"),
    editorialFetch<Report[]>(token, "/zgloszenia"),
    editorialFetch<Alarm[]>(token, "/alarmy"),
  ]);
  const openAlarms = alarms.filter((a) => a.resolved_at === null);
  const waiting = contents.filter((c) => c.state !== "opublikowany" && c.state !== "cofniety");
  const published = contents.filter((c) => c.state === "opublikowany");
  return (
    <div className="pb-stack-5">
      <div className="pb-page-head" style={{ marginBottom: 0 }}>
        <h1 className="ui-title">Panel redakcji</h1>
        <div className="ui-small" style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
          <span>
            Zalogowano: <strong>{me.name}</strong> ({me.roles.join(", ")}).
          </span>
          <form action={editorLogout}>
            <button type="submit" className="pb-btn pb-btn-quiet pb-expert">
              <Icon name="log-out" />
              <span>Wyloguj</span>
            </button>
          </form>
        </div>
      </div>

      {openAlarms.length > 0 ? (
        <section aria-labelledby="alarmy" className="pb-stack-4">
          <h2 id="alarmy" className="ui-heading">
            Alarmy źródła ({openAlarms.length})
          </h2>
          <p className="ui-small pb-muted">
            Synchronizacja jest wstrzymana, a wszystkie karty pokazują „Nie potwierdzono aktualności”. Zamknij alarm dopiero po
            sprawdzeniu zmiany w ELI i poprawieniu kontraktu.
          </p>
          <ul className="pb-list">
            {openAlarms.map((a) => (
              <li key={a.id} className="pb-list-item pb-stack-2">
                <p className="ui-body">
                  <strong>{a.title}</strong> <span className="meta-small">{dateTime(a.raised_at)}</span>
                </p>
                {a.details.adres ? <p className="meta-small">{a.details.adres}</p> : null}
                {a.details.naruszenia?.length ? (
                  <ul className="pb-plain-list ui-small">
                    {a.details.naruszenia.map((v, i) => (
                      <li key={i}>
                        <span className="meta-small">{v.kod}</span> — {v.opis}
                      </li>
                    ))}
                  </ul>
                ) : null}
                <CloseAlarmForm id={a.id} />
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-labelledby="zadania" className="pb-stack-4">
        <h2 id="zadania" className="ui-heading">
          Zadania ({tasks.length})
        </h2>
        {tasks.length === 0 ? (
          <p className="ui-body pb-muted">Brak otwartych zadań.</p>
        ) : (
          <div className="pb-table-wrap" tabIndex={0} role="region" aria-label="Tabela — przewiń w poziomie, jeśli się nie mieści">
            <table className="pb-table ui-small">
              <thead>
                <tr>
                  <th scope="col">Zadanie</th>
                  <th scope="col">Termin</th>
                  <th scope="col">Działanie</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((t) => (
                  <tr key={t.id}>
                    <td>
                      {t.title}
                      <div className="pb-muted meta-small">utworzono {dateTime(t.created_at)}</div>
                    </td>
                    <td className="meta-small">{shortDate(t.due_on) ?? "—"}</td>
                    <td>
                      {t.kind === "przepisy_przejsciowe" && t.act_slug ? (
                        <TransitionalTask task={t} />
                      ) : (
                        <CloseTaskForm id={t.id} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="obieg" className="pb-stack-4">
        <h2 id="obieg" className="ui-heading">
          Treści w obiegu ({waiting.length})
        </h2>
        <p className="ui-small pb-muted">Autor nie zatwierdza własnej treści — zatwierdza niezależny recenzent.</p>
        {waiting.length === 0 ? (
          <p className="ui-body pb-muted">Nic nie czeka na recenzję.</p>
        ) : (
          <ContentTable rows={waiting} />
        )}
      </section>

      <section aria-labelledby="teksty" className="pb-stack-4">
        <h2 id="teksty" className="ui-heading">
          Teksty do kontroli ({texts.length})
        </h2>
        {texts.length === 0 ? (
          <p className="ui-body pb-muted">Brak — parser nie zgłosił tekstów niskiej jakości ani tekstów tylko w PDF.</p>
        ) : (
          <ul className="pb-list">
            {texts.map((t) => (
              <li key={t.id} className="pb-list-item">
                <p className="ui-body">
                  {t.akt}: <span className="meta-small">{t.publikator}</span>
                  {t.jakosc !== null ? <span className="pb-muted"> · jakość parsera {t.jakosc.toLocaleString("pl-PL")}</span> : null}
                </p>
                {t.uwagi ? <p className="ui-small pb-muted">{t.uwagi}</p> : null}
                <TextDecisionForm id={t.id} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="zgloszenia" className="pb-stack-4">
        <h2 id="zgloszenia" className="ui-heading">
          Zgłoszenia błędów ({reports.length})
        </h2>
        {reports.length === 0 ? (
          <p className="ui-body pb-muted">Brak zgłoszeń.</p>
        ) : (
          <div className="pb-table-wrap" tabIndex={0} role="region" aria-label="Tabela — przewiń w poziomie, jeśli się nie mieści">
            <table className="pb-table ui-small">
              <thead>
                <tr>
                  <th scope="col">Numer</th>
                  <th scope="col">Dotyczy</th>
                  <th scope="col">Treść</th>
                  <th scope="col">Termin</th>
                  <th scope="col">Stan</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => (
                  <tr key={r.number}>
                    <td className="meta-small">{r.number}</td>
                    <td>
                      <a href={r.target_path}>{r.target_label || r.target_path}</a>
                    </td>
                    <td>
                      {r.message}
                      {r.has_email ? <div className="pb-muted">czeka na odpowiedź e-mailem</div> : null}
                    </td>
                    <td className="meta-small">{shortDate(r.due_on)}</td>
                    <td>{r.state}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="opublikowane" className="pb-stack-4">
        <h2 id="opublikowane" className="ui-heading">
          Opublikowane ({published.length})
        </h2>
        <ContentTable rows={published} />
      </section>
    </div>
  );
}

function ContentTable({ rows }: { rows: Content[] }) {
  return (
    <div className="pb-table-wrap" tabIndex={0} role="region" aria-label="Tabela — przewiń w poziomie, jeśli się nie mieści">
      <table className="pb-table ui-small">
        <thead>
          <tr>
            <th scope="col">Treść</th>
            <th scope="col">Stan</th>
            <th scope="col">Autor / recenzent</th>
            <th scope="col">Działanie</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={`${c.entity}-${c.id}`}>
              <td>
                {c.label} <span className="pb-muted">(wersja {c.version_no})</span>
                {c.is_demo ? <div className="pb-muted">demonstracyjna</div> : null}
              </td>
              <td>{STATE[c.state] ?? c.state}</td>
              <td>
                {c.author}
                {c.reviewer ? ` / ${c.reviewer}` : ""}
              </td>
              <td>
                <TransitionForm entity={c.entity} id={c.id} state={c.state} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Akt uchylony: kandydaci na przepisy przejściowe z aktu uchylającego i decyzja recenzenta (arkusz, 2.4). */
function TransitionalTask({ task }: { task: Task }) {
  const d = task.details;
  const candidates = d.kandydaci ?? [];
  const source = d.publikator ?? d.akt_uchylajacy ?? "akt uchylający";
  return (
    <div className="pb-stack-2">
      {d.blad ? <p className="ui-small">Nie udało się pobrać aktu uchylającego: {d.blad}</p> : null}
      {candidates.length === 0 ? (
        <p className="ui-small pb-muted">Automat nie znalazł w {source} przepisu o dalszym stosowaniu — sprawdź akt ręcznie.</p>
      ) : (
        <details>
          <summary className="ui-small">
            Kandydaci z {source} ({candidates.length})
          </summary>
          <ul className="pb-plain-list ui-small">
            {candidates.map((c) => (
              <li key={c.klucz}>
                <strong>{c.jednostka}</strong> — {c.tekst}
              </li>
            ))}
          </ul>
        </details>
      )}
      <TransitionalForm
        taskId={task.id}
        actSlug={task.act_slug ?? ""}
        since={d.od ?? null}
        basis={candidates[0] ? `${candidates[0].jednostka} (${source})` : ""}
      />
      <CloseTaskForm id={task.id} />
    </div>
  );
}
