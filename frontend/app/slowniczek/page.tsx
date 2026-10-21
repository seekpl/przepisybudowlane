import type { Metadata } from "next";
import Link from "next/link";

import { StatusBadge } from "@/components/ds/Badges";
import { Drawing, isDrawing } from "@/components/ds/Drawing";
import { Icon } from "@/components/ds/Icon";
import { LawText } from "@/components/ds/LawText";
import { api } from "@/lib/api";
import { typo } from "@/lib/format";

export const metadata: Metadata = { title: "Słowniczek" };

export default async function Page() {
  const [terms, definitions] = await Promise.all([api.glossary(), api.definitions()]);
  const demo = terms.some((t) => t.is_demo);
  return (
    <>
      <div className="pb-page-head">
        <h1 className="ui-display">Słowniczek</h1>
        <p className="ui-body">
          {typo("Najpierw definicje ustawowe — dosłownie, tak jak stoją w przepisach. Niżej pojęcia prostym językiem: to objaśnienia nieurzędowe.")}
        </p>
      </div>

      <section aria-labelledby="definicje" className="pb-section">
        <h2 id="definicje" className="ui-title">
          Definicje ustawowe
        </h2>
        {definitions.length === 0 ? (
          <p className="ui-body pb-muted pb-measure">
            {typo("Pokażemy je, gdy redakcja sprawdzi teksty aktów pobrane z ELI. Do tego czasu definicje znajdziesz w przepisach podanych przy hasłach poniżej.")}
          </p>
        ) : (
          <>
            <nav aria-label="Definicje ustawowe — hasła" className="pb-panel pb-panel-sunken" style={{ marginBottom: "var(--space-4)" }}>
              <ul className="pb-link-row ui-small" style={{ listStyle: "none", padding: 0 }}>
                {definitions.map((d) => (
                  <li key={d.unit_slug}>
                    <a href={`#def-${d.unit_slug}`}>{d.term}</a>
                  </li>
                ))}
              </ul>
            </nav>
            <div className="pb-terms">
              {definitions.map((d) => (
                <section key={d.unit_slug} id={`def-${d.unit_slug}`} className="pb-term pb-panel" aria-labelledby={`def-${d.unit_slug}-h`} tabIndex={-1}>
                  <h3 id={`def-${d.unit_slug}-h`} className="ui-heading">
                    {d.term}
                  </h3>
                  <LawText paragraphs={d.paragraphs} />
                  <p className="ui-small pb-def-meta">
                    <Link href={d.url}>
                      {d.display_label} · {d.journal}
                    </Link>
                    <StatusBadge status={d.freshness} />
                  </p>
                </section>
              ))}
            </div>
          </>
        )}
      </section>

      <section aria-labelledby="objasnienia" className="pb-section">
        <h2 id="objasnienia" className="ui-title">
          Prostym językiem
        </h2>
        <p className="pb-explain-label ui-label" style={{ color: "var(--explain-ink)" }}>
          <Icon name="message-square-text" />
          Objaśnienia nieurzędowe{demo ? " · treść demonstracyjna, bez recenzji prawnej" : ""}
        </p>
      <nav aria-label="Hasła" className="pb-panel pb-panel-sunken" style={{ marginBottom: "var(--space-5)" }}>
        <ul className="pb-link-row ui-small" style={{ listStyle: "none", padding: 0 }}>
          {terms.map((t) => (
            <li key={t.slug}>
              <a href={`#${t.slug}`}>{t.term}</a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="pb-terms">
        {terms.map((t) => (
          <section key={t.slug} id={t.slug} className="pb-term pb-panel" aria-labelledby={`${t.slug}-h`} tabIndex={-1}>
            <h3 id={`${t.slug}-h`} className="ui-heading">
              {t.term}
            </h3>
            <p className="ui-body pb-measure">{typo(t.definition)}</p>
            {t.basis ? (
              <p className="ui-small" style={{ marginTop: "var(--space-2)" }}>
                <span className="pb-muted">Podstawa: </span>
                <span>{t.basis}</span>
              </p>
            ) : null}
            {t.units.length > 0 ? (
              <p className="ui-small">
                {t.units.map((u, i) => (
                  <span key={u.slug}>
                    {i > 0 ? " · " : ""}
                    <Link href={u.url}>Przepis: {u.display_label}</Link>
                  </span>
                ))}
              </p>
            ) : null}
            {isDrawing(t.illustration) ? (
              <div style={{ marginTop: "var(--space-3)" }}>
                <Drawing name={t.illustration} idSuffix={`-${t.slug}`} />
              </div>
            ) : null}
            {t.see_also.length > 0 ? (
              <p className="ui-small pb-muted" style={{ marginTop: "var(--space-2)" }}>
                Zobacz też:{" "}
                {t.see_also.map((s, i) => (
                  <span key={s.slug}>
                    {i > 0 ? ", " : ""}
                    <a href={`#${s.slug}`}>{s.term}</a>
                  </span>
                ))}
              </p>
            ) : null}
          </section>
        ))}
      </div>
      </section>
    </>
  );
}
