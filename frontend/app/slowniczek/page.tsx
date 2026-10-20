import type { Metadata } from "next";
import Link from "next/link";

import { Drawing, isDrawing } from "@/components/ds/Drawing";
import { Icon } from "@/components/ds/Icon";
import { api } from "@/lib/api";
import { typo } from "@/lib/format";

export const metadata: Metadata = { title: "Słowniczek" };

export default async function Page() {
  const terms = await api.glossary();
  const demo = terms.some((t) => t.is_demo);
  return (
    <>
      <div className="pb-page-head">
        <h1 className="ui-display">Słowniczek</h1>
        <p className="ui-body">
          {typo("Pojęcia z ustaw prostym językiem. Brzmienie ustawowe znajdziesz w przepisie podanym przy każdym haśle.")}
        </p>
        <p className="pb-explain-label ui-label" style={{ color: "var(--explain-ink)" }}>
          <Icon name="message-square-text" />
          Objaśnienia nieurzędowe{demo ? " · treść demonstracyjna, bez recenzji prawnej" : ""}
        </p>
      </div>
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
            <h2 id={`${t.slug}-h`} className="ui-title">
              {t.term}
            </h2>
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
    </>
  );
}
