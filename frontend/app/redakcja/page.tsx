import type { Metadata } from "next";

import { editorDecideRule, editorDismissMiss, editorLogout } from "@/app/actions";
import { AiDraftDecisionForm, AiDraftRequestForm, CloseAlarmForm, CloseTaskForm, LoginForm, SynonymForm, TextDecisionForm, TransitionalForm, TransitionForm } from "@/components/editorial/Forms";
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
interface WizardRule {
  id: number;
  jednostka: string;
  adres: string | null;
  obiekt: string;
  wymog: string;
  warunki: string[];
}
interface Miss {
  id: number;
  zapytanie: string;
  liczba: number;
  propozycje: string[];
}
interface Citation {
  akapit: string;
  przepis: string | null;
  cytat: string;
}
interface DiffPart {
  typ: "bez_zmian" | "usuniete" | "dodane";
  tekst: string;
  skrot?: boolean;
  cytaty?: Citation[];
}
interface AiDraft {
  id: number;
  wersja: number;
  akt: string;
  przepis: string;
  przepis_slug: string;
  model: string;
  utworzono: string;
  tekst_urzedowy: string | null;
  zmiana_przepisu: DiffPart[] | null;
  poprzednie_objasnienie: { wersja: number; stan: string } | null;
  zmiana_objasnienia: DiffPart[];
  odrzucone: { tekst: string; bledy: string[] }[];
  uwagi: string | null;
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
  const [tasks, contents, texts, reports, alarms, misses, rules, drafts] = await Promise.all([
    editorialFetch<Task[]>(token, "/zadania"),
    editorialFetch<Content[]>(token, "/tresci"),
    editorialFetch<TextReview[]>(token, "/teksty"),
    editorialFetch<Report[]>(token, "/zgloszenia"),
    editorialFetch<Alarm[]>(token, "/alarmy"),
    editorialFetch<Miss[]>(token, "/propozycje-synonimow"),
    editorialFetch<WizardRule[]>(token, "/reguly-kreatora"),
    editorialFetch<AiDraft[]>(token, "/szkice-ai"),
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

      <section aria-labelledby="szkice-ai" className="pb-stack-4">
        <h2 id="szkice-ai" className="ui-heading">
          Szkice AI do recenzji ({drafts.length})
        </h2>
        <p className="ui-small pb-muted">
          Szkic napisało AI wyłącznie z tekstu z ELI. Każde zdanie ma cytat sprawdzony automatycznie; zdania bez pokrycia w przepisie
          zostały odrzucone. Widzisz tylko różnice. Zatwierdzenie publikuje objaśnienie z Twoim nazwiskiem — szkic nigdy nie publikuje
          się sam.
        </p>
        {drafts.length === 0 ? (
          <p className="ui-body pb-muted">Brak — nowe szkice powstają po zmianie brzmienia opublikowanego objaśnienia albo na zlecenie.</p>
        ) : (
          <ul className="pb-list">
            {drafts.map((d) => (
              <AiDraftItem key={d.id} draft={d} />
            ))}
          </ul>
        )}
        {me.roles.includes("redaktor") ? (
          <details>
            <summary className="ui-small">Zleć szkic AI dla innego przepisu</summary>
            <AiDraftRequestForm />
          </details>
        ) : null}
      </section>

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

      <section aria-labelledby="reguly" className="pb-stack-4">
        <h2 id="reguly" className="ui-heading">
          Reguły kreatora do przeglądu ({rules.length})
        </h2>
        <p className="ui-small pb-muted">
          Automat odczytał punkty art. 29 Prawa budowlanego jako reguły. Do kreatora trafia tylko reguła zatwierdzona przez recenzenta;
          gdy brzmienie punktu się zmieni, reguła wraca tutaj.
        </p>
        {rules.length === 0 ? (
          <p className="ui-body pb-muted">Brak — wszystkie reguły mają decyzję albo tekst art. 29 czeka na kontrolę.</p>
        ) : (
          <div className="pb-table-wrap" tabIndex={0} role="region" aria-label="Tabela — przewiń w poziomie, jeśli się nie mieści">
            <table className="pb-table ui-small">
              <thead>
                <tr>
                  <th scope="col">Przepis</th>
                  <th scope="col">Obiekt i warunki</th>
                  <th scope="col">Wymóg</th>
                  <th scope="col">Decyzja</th>
                </tr>
              </thead>
              <tbody>
                {rules.slice(0, 40).map((r) => (
                  <tr key={r.id}>
                    <td>{r.adres ? <a href={r.adres}>{r.jednostka}</a> : r.jednostka}</td>
                    <td>
                      {r.obiekt}
                      {r.warunki.length > 0 ? <div className="pb-muted">{r.warunki.join("; ")}</div> : null}
                    </td>
                    <td>{r.wymog}</td>
                    <td>
                      <form action={editorDecideRule} className="pb-link-row">
                        <input type="hidden" name="rule_id" value={r.id} />
                        <button type="submit" name="decision" value="zatwierdz" className="pb-btn pb-btn-secondary pb-expert">
                          <span>Zatwierdź</span>
                        </button>
                        <button type="submit" name="decision" value="odrzuc" className="pb-btn pb-btn-quiet pb-expert">
                          <span>Odrzuć</span>
                        </button>
                      </form>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section aria-labelledby="bez-wynikow" className="pb-stack-4">
        <h2 id="bez-wynikow" className="ui-heading">
          Zapytania bez wyników ({misses.length})
        </h2>
        <p className="ui-small pb-muted">
          Zapisujemy tylko treść zapytania i liczbę wystąpień — bez danych o osobie. Podpowiedzi to słowa z indeksu podobne do szukanego.
        </p>
        {misses.length === 0 ? (
          <p className="ui-body pb-muted">Brak — każde zapytanie coś znalazło.</p>
        ) : (
          <ul className="pb-list">
            {misses.map((m) => (
              <li key={m.id} className="pb-list-item pb-stack-2">
                <p className="ui-body">
                  <strong>„{m.zapytanie}”</strong> <span className="meta-small">{m.liczba} ×</span>
                </p>
                <SynonymForm missId={m.id} term={m.zapytanie} suggestions={m.propozycje} />
                <form action={editorDismissMiss}>
                  <input type="hidden" name="miss_id" value={m.id} />
                  <button type="submit" className="pb-btn pb-btn-quiet pb-expert">
                    <span>Odrzuć — synonim niepotrzebny</span>
                  </button>
                </form>
              </li>
            ))}
          </ul>
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

function Diff({ parts }: { parts: DiffPart[] }) {
  return (
    <p className="pb-diff ui-small">
      {parts.map((p, i) =>
        p.typ === "dodane" ? (
          <ins key={i}>{p.tekst} </ins>
        ) : p.typ === "usuniete" ? (
          <del key={i}>{p.tekst} </del>
        ) : (
          <span key={i} className="pb-muted">
            {p.tekst}{" "}
          </span>
        ),
      )}
    </p>
  );
}

/** Szkic AI w kolejce: zmiana brzmienia po słowach, zmiana objaśnienia po zdaniach z cytatami, odrzucone zdania (3.6). */
function AiDraftItem({ draft: d }: { draft: AiDraft }) {
  const unchanged = d.zmiana_objasnienia.filter((p) => p.typ === "bez_zmian").length;
  const changed = d.zmiana_objasnienia.filter((p) => p.typ !== "bez_zmian");
  return (
    <li className="pb-list-item pb-stack-3">
      <p className="ui-body">
        <strong>
          {d.akt}, <a href={`/przepis/${d.przepis_slug}`}>{d.przepis}</a>
        </strong>{" "}
        <span className="meta-small">
          wersja {d.wersja} · {d.tekst_urzedowy ?? "tekst z ELI"} · szkic {d.model}, {dateTime(d.utworzono)}
        </span>
      </p>
      {d.zmiana_przepisu ? (
        <div className="pb-stack-1">
          <h3 className="ui-label">Zmiana w przepisie</h3>
          <Diff parts={d.zmiana_przepisu} />
        </div>
      ) : (
        <p className="ui-small pb-muted">
          {d.poprzednie_objasnienie
            ? "Brzmienie przepisu się nie zmieniło — szkic zlecony przez redakcję."
            : "Pierwsze objaśnienie tego przepisu — brak poprzedniej wersji do porównania."}
        </p>
      )}
      <div className="pb-stack-1">
        <h3 className="ui-label">
          Zmiana w objaśnieniu
          {d.poprzednie_objasnienie ? ` (wobec wersji ${d.poprzednie_objasnienie.wersja})` : ""}
        </h3>
        <ul className="pb-plain-list ui-small pb-diff">
          {changed.map((p, i) => (
            <li key={i} className="pb-diff-sentence">
              {p.typ === "dodane" ? <ins>{p.tekst}</ins> : <del>{p.tekst}</del>}
              {p.cytaty?.length ? (
                <ul className="pb-plain-list pb-diff-quotes">
                  {p.cytaty.map((c, j) => (
                    <li key={j} className="meta-small">
                      {c.przepis ?? c.akapit}: „{c.cytat}”
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
        {unchanged > 0 ? <p className="meta-small pb-muted">Bez zmian: {unchanged} zdań.</p> : null}
      </div>
      {d.odrzucone.length > 0 ? (
        <details>
          <summary className="ui-small">Odrzucone przez walidatory ({d.odrzucone.length})</summary>
          <ul className="pb-plain-list ui-small">
            {d.odrzucone.map((r, i) => (
              <li key={i}>
                {r.tekst} <span className="pb-muted">— {r.bledy.join(" ")}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {d.uwagi ? <p className="ui-small pb-muted">Uwagi modelu: {d.uwagi}</p> : null}
      <AiDraftDecisionForm id={d.id} />
    </li>
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
