import type { Metadata } from "next";
import Link from "next/link";

import { SearchForm } from "@/components/site/SearchForm";
import { api } from "@/lib/api";
import { typo } from "@/lib/format";
import { getMode } from "@/lib/mode";

export const metadata: Metadata = { title: "Szukaj" };

export default async function SearchPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const query = q.trim().slice(0, 200);
  const [mode, result] = await Promise.all([getMode(), query ? api.search(query) : Promise.resolve(null)]);
  return (
    <>
      <div className="pb-page-head">
        <h1 className="ui-display">{query ? `Wyniki dla „${query}”` : "Szukaj w przepisach"}</h1>
        <p className="ui-body">
          {typo("Szukamy w odmianie i bez polskich znaków. Potoczne słowa zamieniamy na ustawowe według jawnego słownika.")}{" "}
          <Link href="/o-serwisie#synonimy">Zobacz słownik</Link>
        </p>
      </div>
      <SearchForm mode={mode} defaultValue={query} label="Szukane słowa" />
      {result ? (
        <section className="pb-section" aria-labelledby="wyniki" style={{ marginTop: "var(--space-6)" }}>
          <h2 id="wyniki" className="pb-sr">
            Wyniki
          </h2>
          <div role="status" className="pb-stack-2" style={{ marginBottom: "var(--space-4)" }}>
            {result.synonyms_used.map((s) => (
              <p key={s.slowo} className="ui-small pb-muted">
                {`Szukamy też: ${s.szukamy_tez.join(", ")} (dla „${s.slowo}”).`}
              </p>
            ))}
            {result.hits.length > 0 && !result.matched_all_words ? (
              <p className="ui-small">Żaden wynik nie zawiera wszystkich słów. Pokazujemy te, które zawierają część z nich.</p>
            ) : null}
            <p className="ui-small pb-muted">
              {result.hits.length === 0 ? "Brak wyników." : `Wyniki: ${result.hits.length}.`}
            </p>
          </div>
          {result.hits.length === 0 ? (
            <div className="pb-panel pb-stack-2">
              <p className="ui-heading">Nic nie znaleźliśmy</p>
              <p className="ui-body pb-measure">
                {typo("Spróbuj innego słowa albo krótszego zapytania. Jeśli pytasz o budowę domu, zacznij od kreatora.")}
              </p>
              <p className="ui-body">
                <Link href="/kreator/pozwolenie-zgloszenie">Czy potrzebuję pozwolenia na budowę?</Link>
              </p>
            </div>
          ) : (
            <ol className="pb-list">
              {result.hits.map((h) => (
                <li key={`${h.kind}-${h.ref}`} className="pb-list-item">
                  <p className="ui-label pb-hit-kind">{h.kind_label}</p>
                  <h3 className="ui-heading">
                    <Link href={h.url}>{h.title}</Link>
                  </h3>
                  {h.subtitle && h.subtitle !== h.title ? <p className="meta-small pb-muted">{h.subtitle}</p> : null}
                  <p className="ui-body pb-measure">{h.snippet}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
      ) : null}
    </>
  );
}
