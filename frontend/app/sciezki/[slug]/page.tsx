import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Drawing, isDrawing } from "@/components/ds/Drawing";
import { Explanation } from "@/components/ds/Explanation";
import { ErrorReportForm } from "@/components/site/ErrorReportForm";
import { api } from "@/lib/api";
import { shortDate, typo } from "@/lib/format";
import { getMode } from "@/lib/mode";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const g = await api.guide((await params).slug);
  return { title: g?.title ?? "Ścieżka" };
}

export default async function Page({ params }: Props) {
  const { slug } = await params;
  const [g, mode] = await Promise.all([api.guide(slug), getMode()]);
  if (!g) notFound();
  return (
    <>
      <nav className="pb-crumbs ui-small" aria-label="Okruszki">
        <ol>
          <li>
            <Link href="/sciezki">Krok po kroku</Link>
          </li>
          <li aria-current="page">{g.title}</li>
        </ol>
      </nav>
      <div className="pb-detail">
        <div className="pb-stack-5">
          <div className="pb-page-head" style={{ marginBottom: 0 }}>
            <h1 className="ui-display">{g.title}</h1>
            <p className="ui-body">{typo(g.summary)}</p>
          </div>
          <Explanation
            mode={mode}
            title="Zanim zaczniesz"
            footer={
              g.is_demo ? (
                <span className="pb-demo-label">Ścieżka demonstracyjna — nie przeszła recenzji prawnej.</span>
              ) : (
                <span>Zweryfikowano {shortDate(g.verified_on)}.</span>
              )
            }
          >
            <p>{typo(g.caveat ?? "To informacja, nie porada prawna.")}</p>
          </Explanation>
          <ol className="pb-steps-list" aria-label="Kroki">
            {g.steps.map((st, i) => (
              <li key={i}>
                <div className="pb-step-body">
                  <h2 className="ui-heading">{typo(st.title)}</h2>
                  <p className="ui-body pb-measure">{typo(st.body)}</p>
                  <dl className="pb-dl ui-small">
                    {st.who ? (
                      <>
                        <dt>Kto</dt>
                        <dd>{typo(st.who)}</dd>
                      </>
                    ) : null}
                    {st.documents.length > 0 ? (
                      <>
                        <dt>Dokumenty</dt>
                        <dd>
                          <ul className="pb-plain-list">
                            {st.documents.map((d) => (
                              <li key={d}>{typo(d)}</li>
                            ))}
                          </ul>
                        </dd>
                      </>
                    ) : null}
                    {st.basis ? (
                      <>
                        <dt>Podstawa</dt>
                        <dd>{st.basis}</dd>
                      </>
                    ) : null}
                  </dl>
                  {st.unit || st.link ? (
                    <p className="ui-small">
                      {st.unit ? <Link href={st.unit.url}>Przepis: {st.unit.display_label}</Link> : null}
                      {st.unit && st.link ? " · " : null}
                      {st.link ? <Link href={st.link}>{st.link.startsWith("/kreator") ? "Sprawdź w kreatorze" : "Więcej"}</Link> : null}
                    </p>
                  ) : null}
                  {isDrawing(st.illustration) ? <Drawing name={st.illustration} idSuffix={`-${i}`} /> : null}
                </div>
              </li>
            ))}
          </ol>
        </div>
        <aside className="pb-aside" aria-label="Powiązane">
          {g.units.length > 0 ? (
            <section className="pb-panel" aria-labelledby="przepisy">
              <h2 id="przepisy" className="ui-heading">
                Przepisy w tej ścieżce
              </h2>
              <ul className="pb-plain-list ui-body">
                {g.units.map((u) => (
                  <li key={u.slug}>
                    <Link href={u.url}>{u.title ?? u.display_label}</Link>{" "}
                    <span className="meta-small pb-muted">{u.display_label}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <section className="pb-panel" aria-labelledby="zglos">
            <h2 id="zglos" className="ui-heading">
              Zgłoś błąd
            </h2>
            <ErrorReportForm mode={mode} targetPath={`/sciezki/${g.slug}`} targetLabel={g.title} />
          </section>
        </aside>
      </div>
    </>
  );
}
