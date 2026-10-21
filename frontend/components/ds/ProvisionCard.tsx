import Link from "next/link";

import { shortDate, typo } from "@/lib/format";
import type { Mode, Provision } from "@/lib/types";

import { StatusBadge, TextTypeBadge } from "./Badges";
import { Citation } from "./Citation";
import { Drawing, isDrawing } from "./Drawing";
import { Explanation } from "./Explanation";
import { FreshnessNotice, FreshnessNotices } from "./FreshnessNotice";
import { LawText } from "./LawText";

function ExplanationBlock({ p, mode }: { p: Provision; mode: Mode }) {
  if (p.explanation_status === "zawieszone") {
    return (
      <FreshnessNotice status="niepotwierdzona" mode={mode} title="Objaśnienie czeka na ponowne sprawdzenie">
        <p className={mode === "simple" ? "ui-body" : "ui-small"}>
          {typo(p.explanation?.suspended_reason ?? "Przepis zmienił się po napisaniu objaśnienia.")} Do czasu weryfikacji
          pokazujemy tylko oficjalne brzmienie.
        </p>
      </FreshnessNotice>
    );
  }
  if (p.explanation_status === "cofniete" || !p.explanation) return null;
  const e = p.explanation;
  const footer = (
    <>
      {e.is_demo ? (
        <span className="pb-demo-label">Treść demonstracyjna — nie przeszła recenzji prawnej. </span>
      ) : null}
      <span>
        Wersja {e.version_no}
        {e.verified_on ? `, zweryfikowano ${shortDate(e.verified_on)}` : ""}
        {e.reviewer ? ` (${e.reviewer})` : ""}. Informacja, nie porada prawna.
      </span>
    </>
  );
  return (
    <Explanation title={e.title} mode={mode} footer={footer}>
      {e.paragraphs.map((t, i) => (
        <p key={i}>{typo(t)}</p>
      ))}
    </Explanation>
  );
}

/**
 * Karta przepisu — główny widok produktu. Kolejność stała: nagłówek z odznakami → komunikat o aktualności → treść.
 * Prosty: objaśnienie, oficjalne brzmienie, metryka. Ekspercki: metryka, tekst, objaśnienie.
 */
export function ProvisionCard({ p, mode, headingLevel = 1 }: { p: Provision; mode: Mode; headingLevel?: 1 | 2 }) {
  const Heading = headingLevel === 1 ? "h1" : "h2";
  const law = (
    <LawText mode={mode} paragraphs={p.paragraphs}>
      {p.text_note && mode === "expert" ? <p className="ui-small pb-muted pb-law-note">{p.text_note}</p> : null}
    </LawText>
  );
  const drawing = isDrawing(p.illustration) ? <Drawing name={p.illustration} /> : null;
  const explanation = (
    <>
      <ExplanationBlock p={p} mode={mode} />
      {drawing}
    </>
  );
  const cite = <Citation citation={p.citation} mode={mode} />;
  return (
    <article className={`pb-card pb-${mode}`} aria-labelledby="karta-tytul">
      <header className="pb-card-head">
        <p className={mode === "simple" ? "meta" : "meta-small pb-muted"}>{p.display_label}</p>
        <Heading id="karta-tytul" className={mode === "simple" ? "ui-title" : "ui-heading"}>
          {p.title ?? `${p.act.short_title}, ${p.label}`}
        </Heading>
        <div className="pb-badges">
          <StatusBadge status={p.freshness.status} date={p.freshness.date} effectiveDate={p.freshness.effective_date} />
          {/* Bez brzmienia nie ma czego opisywać typem — powód podaje komunikat (np. tekst czeka na kontrolę). */}
          {p.paragraphs.length > 0 ? <TextTypeBadge type={p.text_type} /> : null}
        </div>
        {p.is_archived_version ? (
          <p className="ui-small">
            <Link href={p.current_url}>Przejdź do najnowszej wersji tego przepisu</Link>
          </p>
        ) : null}
      </header>
      <FreshnessNotices notices={p.freshness.notices} mode={mode} />
      {mode === "simple" ? (
        <>
          {explanation}
          {p.paragraphs.length > 0 ? (
            <>
              <h2 className="pb-law-heading ui-label">Oficjalne brzmienie</h2>
              {law}
            </>
          ) : null}
          {cite}
        </>
      ) : (
        <>
          {cite}
          {p.paragraphs.length > 0 ? (
            <>
              <h2 className="pb-sr">Oficjalne brzmienie</h2>
              {law}
            </>
          ) : null}
          {explanation}
        </>
      )}
    </article>
  );
}
