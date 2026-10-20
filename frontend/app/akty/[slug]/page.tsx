import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { StatusBadge, TextTypeBadge } from "@/components/ds/Badges";
import { ButtonLink } from "@/components/ds/Button";
import { FreshnessNotices } from "@/components/ds/FreshnessNotice";
import { api } from "@/lib/api";
import { dateTime, shortDate } from "@/lib/format";
import { getMode } from "@/lib/mode";

type Props = { params: Promise<{ slug: string }> };

const REVIEW: Record<string, string> = {
  zaakceptowany: "zaakceptowany",
  do_kontroli: "czeka na kontrolę człowieka",
  odrzucony: "odrzucony",
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const a = await api.act((await params).slug);
  return { title: a?.short_title ?? "Akt" };
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  const [a, mode] = await Promise.all([api.act(slug), getMode()]);
  if (!a) notFound();
  const tv = a.current_text;
  return (
    <>
      <nav className="pb-crumbs ui-small" aria-label="Okruszki">
        <ol>
          <li>
            <Link href="/akty">Akty</Link>
          </li>
          <li aria-current="page">{a.short_title}</li>
        </ol>
      </nav>
      <div className="pb-detail">
        <div className="pb-stack-5">
          <div className="pb-page-head" style={{ marginBottom: 0 }}>
            <p className="ui-label pb-muted">{a.area}</p>
            <h1 className="ui-title">{a.title}</h1>
            <div className="pb-badges">
              <StatusBadge status={a.freshness.status} date={a.freshness.date} effectiveDate={a.freshness.effective_date} />
              {tv ? <TextTypeBadge type={tv.text_type} /> : null}
            </div>
          </div>
          <FreshnessNotices notices={a.freshness.notices} mode={mode} />
          <section className="pb-panel" aria-labelledby="metryka">
            <h2 id="metryka" className="ui-heading">
              Metryka
            </h2>
            <dl className="pb-dl ui-small">
              <dt>ELI aktu</dt>
              <dd className="meta-small">{a.eli}</dd>
              <dt>Rodzaj</dt>
              <dd>{a.act_kind}</dd>
              <dt>Bieżący tekst</dt>
              <dd>
                {tv ? (
                  <>
                    <span className="meta-small">{tv.journal}</span> ({REVIEW[tv.review_state] ?? tv.review_state}
                    {tv.origin === "redakcja" ? ", wprowadzony przez redakcję" : ", z synchronizacji ELI"})
                  </>
                ) : (
                  "brak — tekst pojawi się po synchronizacji z ELI"
                )}
              </dd>
              <dt>Stan prawny</dt>
              <dd className="meta-small">{shortDate(tv?.legal_status_date) ?? "nieznany"}</dd>
              <dt>Ostatnia synchronizacja</dt>
              <dd className="meta-small">{a.last_sync_ok ? dateTime(a.last_sync_ok) : "jeszcze nie było"}</dd>
              <dt>Właściciel merytoryczny</dt>
              <dd>{a.owner ?? "—"}</dd>
              <dt>Manifest zweryfikowano</dt>
              <dd className="meta-small">{shortDate(a.manifest_verified_on) ?? "jeszcze nie"}</dd>
            </dl>
            {tv?.note ? (
              <p className="ui-small pb-muted" style={{ marginTop: "var(--space-2)" }}>
                {tv.note}
              </p>
            ) : null}
            <div className="pb-link-row" style={{ marginTop: "var(--space-3)" }}>
              <ButtonLink href={a.official_url} external variant="secondary" mode={mode} icon="external-link">
                Otwórz oficjalny tekst
              </ButtonLink>
            </div>
          </section>
          <section className="pb-panel" aria-labelledby="nowelizacje">
            <h2 id="nowelizacje" className="ui-heading">
              Wykryte nowelizacje
            </h2>
            {a.amendments.length === 0 ? (
              <p className="ui-small pb-muted">Brak — lista powstaje automatycznie z ELI podczas synchronizacji.</p>
            ) : (
              <div className="pb-table-wrap" tabIndex={0} role="region" aria-label="Tabela — przewiń w poziomie, jeśli się nie mieści">
                <table className="pb-table ui-small">
                  <thead>
                    <tr>
                      <th scope="col">Publikator</th>
                      <th scope="col">Ogłoszono</th>
                      <th scope="col">Obowiązuje od</th>
                      <th scope="col">Względem tekstu</th>
                    </tr>
                  </thead>
                  <tbody>
                    {a.amendments.map((am) => (
                      <tr key={am.eli}>
                        <td>
                          <a href={am.url} target="_blank" rel="noopener" className="meta-small">
                            {am.journal}
                          </a>
                        </td>
                        <td className="meta-small">{shortDate(am.published_on) ?? "—"}</td>
                        <td className="meta-small">{shortDate(am.entry_into_force) ?? "nieznane"}</td>
                        <td>{am.later_than_text ? "późniejsza — tekst jej nie zawiera" : "zawarta w tekście"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
        <aside className="pb-aside" aria-label="Przepisy i powiązania">
          <section className="pb-panel" aria-labelledby="karty">
            <h2 id="karty" className="ui-heading">
              Karty przepisów
            </h2>
            {a.units.length === 0 ? (
              <p className="ui-small pb-muted">Redakcja nie przygotowała jeszcze kart dla tego aktu.</p>
            ) : (
              <ul className="pb-plain-list ui-body">
                {a.units.map((u) => (
                  <li key={u.slug}>
                    <Link href={u.url}>{u.title ?? u.label}</Link> <span className="meta-small pb-muted">{u.label}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {a.relations.length > 0 ? (
            <section className="pb-panel" aria-labelledby="powiazania">
              <h2 id="powiazania" className="ui-heading">
                Powiązania z manifestu
              </h2>
              <ul className="pb-plain-list ui-small">
                {a.relations.map((r, i) => (
                  <li key={i}>
                    <span className="pb-muted">{r.rola}: </span>
                    {r.opis}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </aside>
      </div>
    </>
  );
}
