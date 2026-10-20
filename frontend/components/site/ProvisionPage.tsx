import Link from "next/link";

import { textTypeLabel } from "@/components/ds/Badges";
import { Icon } from "@/components/ds/Icon";
import { ProvisionCard } from "@/components/ds/ProvisionCard";
import { dateTime, shortDate, typo } from "@/lib/format";
import type { Mode, Provision } from "@/lib/types";

import { ErrorReportForm } from "./ErrorReportForm";

const VALIDITY: Record<string, string> = {
  obowiazuje: "Obowiązuje",
  utracil_moc: "Utracił moc",
  stosowany_przejsciowo: "Stosowany przejściowo",
  zawieszony: "Zawieszony",
};

const RELATED_LABEL = { sciezka: "Krok po kroku", kreator: "Kreator", pojecie: "Słowniczek" } as const;

function History({ p, mode }: { p: Provision; mode: Mode }) {
  return (
    <div className="pb-stack-2">
      <ul className="pb-plain-list ui-small">
        {p.versions.map((v) => (
          <li key={v.unit_version_id}>
            <Link href={v.permalink}>
              {v.journal} — {textTypeLabel(v.text_type).toLowerCase()}
            </Link>
            {v.is_current ? " (bieżąca)" : ""}
            {mode === "expert" ? <span className="meta-small pb-muted"> · zapisano {dateTime(v.recorded_at)}</span> : null}
          </li>
        ))}
      </ul>
      {p.explanation_versions.length > 0 ? (
        <>
          <p className="ui-label pb-muted">Wersje objaśnienia</p>
          <ul className="pb-plain-list ui-small">
            {p.explanation_versions.map((v) => (
              <li key={v.id}>
                <Link href={v.permalink}>Wersja {v.version_no}</Link>
                {v.verified_on ? `, zweryfikowano ${shortDate(v.verified_on)}` : ""}
                {v.state !== "opublikowany" ? ` (${v.state === "zawieszony" ? "zawieszona" : "cofnięta"})` : ""}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
}

export function ProvisionPage({ p, mode }: { p: Provision; mode: Mode }) {
  const later = p.amendments.filter((a) => a.later_than_text);
  return (
    <>
      <nav className="pb-crumbs ui-small" aria-label="Okruszki">
        <ol>
          <li>
            <Link href="/akty">Akty</Link>
          </li>
          <li>
            <Link href={`/akty/${p.act.slug}`}>{p.act.short_title}</Link>
          </li>
          <li aria-current="page">{p.label}</li>
        </ol>
      </nav>
      <div className="pb-detail">
        <ProvisionCard p={p} mode={mode} />
        <aside className="pb-aside" aria-label="Powiązane i metryka">
          {p.related.length > 0 ? (
            <section className="pb-panel" aria-labelledby="powiazane">
              <h2 id="powiazane" className="ui-heading">
                Zobacz też
              </h2>
              <ul className="pb-plain-list ui-body">
                {p.related.map((r) => (
                  <li key={r.url}>
                    <span className="ui-label pb-muted">{RELATED_LABEL[r.kind]}: </span>
                    <Link href={r.url}>{r.title}</Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {mode === "expert" || later.length > 0 ? (
            <section className="pb-panel" aria-labelledby="nowelizacje">
              <h2 id="nowelizacje" className="ui-heading">
                Wykryte nowelizacje
              </h2>
              {p.amendments.length === 0 ? (
                <p className="ui-small pb-muted">
                  Synchronizacja nie wykryła nowelizacji tego aktu. Lista powstaje automatycznie z ELI.
                </p>
              ) : (
                <ul className="pb-plain-list ui-small">
                  {p.amendments.map((a) => (
                    <li key={a.eli}>
                      <a href={a.url} target="_blank" rel="noopener">
                        {a.journal}
                      </a>
                      {a.entry_into_force ? ` — obowiązuje od ${shortDate(a.entry_into_force)}` : " — data wejścia w życie nieznana"}
                      {a.later_than_text ? <strong> · późniejsza niż pokazany tekst</strong> : ""}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ) : null}

          {p.validity.length > 0 ? (
            <section className="pb-panel" aria-labelledby="obowiazywanie">
              <h2 id="obowiazywanie" className="ui-heading">
                Obowiązywanie
              </h2>
              <dl className="pb-dl ui-small">
                {p.validity.map((v, i) => (
                  <div key={i} style={{ display: "contents" }}>
                    <dt>{VALIDITY[v.kind] ?? v.kind}</dt>
                    <dd>
                      od <span className="meta-small">{shortDate(v.valid_from) ?? "—"}</span>
                      {v.valid_to ? (
                        <>
                          {" "}
                          do <span className="meta-small">{shortDate(v.valid_to)}</span>
                        </>
                      ) : null}
                      {v.basis ? <span className="pb-muted"> · {v.basis}</span> : null}
                    </dd>
                  </div>
                ))}
              </dl>
            </section>
          ) : null}

          <section className="pb-panel" aria-labelledby="historia">
            <h2 id="historia" className="ui-heading">
              Wersje i trwały adres
            </h2>
            <p className="ui-small pb-muted" style={{ marginBottom: "var(--space-2)" }}>
              Każda wersja ma stały adres — możesz go przywołać w aktach sprawy.
            </p>
            {mode === "expert" ? (
              <History p={p} mode={mode} />
            ) : (
              <details className="pb-details">
                <summary className="ui-small">
                  <Icon name="history" />
                  Pokaż wersje
                </summary>
                <History p={p} mode={mode} />
              </details>
            )}
            <p className="ui-small" style={{ marginTop: "var(--space-2)" }}>
              <Icon name="link" /> <Link href={p.permalink}>Adres tej wersji</Link>
            </p>
          </section>

          <section className="pb-panel" aria-labelledby="zglos">
            <h2 id="zglos" className="ui-heading">
              Zgłoś błąd
            </h2>
            <p className="ui-small pb-muted" style={{ marginBottom: "var(--space-3)" }}>
              {typo("Odpowiemy w ciągu 5 dni roboczych. Nie odpowiadamy na pytania o konkretną sprawę — z tym zwróć się do urzędu albo prawnika.")}
            </p>
            <ErrorReportForm mode={mode} targetPath={p.permalink} targetLabel={`${p.display_label} — ${p.title ?? ""}`} unitSlug={p.slug} />
          </section>
        </aside>
      </div>
    </>
  );
}
