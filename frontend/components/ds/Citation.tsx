"use client";

import { useEffect, useRef, useState } from "react";

import { shortDate } from "@/lib/format";
import type { Citation as CitationData, Mode } from "@/lib/types";

import { Button } from "./Button";
import { Icon } from "./Icon";

/** Metryka i cytat: akt, publikator, jednostka, stan na, ELI, link do oficjalnego tekstu, „Kopiuj cytat”. */
export function Citation({ citation, mode = "simple" }: { citation: CitationData; mode?: Mode }) {
  const [copied, setCopied] = useState<"ok" | "blad" | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    const text = citation.url ? `${citation.text} (${citation.url})` : citation.text;
    try {
      await navigator.clipboard.writeText(text);
      setCopied("ok");
    } catch {
      setCopied("blad");
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(null), 2500);
  }

  const rows: [string, string, boolean][] = [
    ["Publikator", citation.journal, true],
    ["Jednostka", citation.unit, false],
    ["Stan na", shortDate(citation.as_of) ?? "nie podano", true],
  ];
  if (citation.eli) rows.push(["ELI", citation.eli, true]);
  const small = mode === "simple" ? "ui-body" : "ui-small";

  return (
    <section className={`pb-cite pb-${mode}`} aria-label="Metryka przepisu">
      <p className={`pb-cite-act ${small}`}>{citation.act}</p>
      <dl className="pb-cite-grid">
        {rows.map(([label, value, mono]) => (
          <div key={label} className="pb-cite-item">
            <dt className="ui-label">{label}</dt>
            <dd className={mono ? (mode === "simple" ? "meta" : "meta-small") : small}>{value}</dd>
          </div>
        ))}
      </dl>
      <div className="pb-cite-actions">
        {citation.url ? (
          <a className={`pb-btn pb-btn-quiet pb-${mode}`} href={citation.url} target="_blank" rel="noopener">
            <Icon name="external-link" />
            <span>Otwórz oficjalny tekst</span>
            <span className="pb-sr"> (otwiera się w nowej karcie)</span>
          </a>
        ) : null}
        <Button variant="quiet" mode={mode} icon={copied === "ok" ? "check" : "copy"} onClick={copy}>
          {copied === "ok" ? "Skopiowano" : "Kopiuj cytat"}
        </Button>
        <span className="pb-sr" role="status">
          {copied === "ok" ? "Cytat skopiowany do schowka" : copied === "blad" ? "Nie udało się skopiować. Zaznacz tekst metryki i skopiuj go ręcznie." : ""}
        </span>
      </div>
      {copied === "blad" ? (
        <p className="ui-small pb-muted">Nie udało się skopiować. Zaznacz tekst metryki i skopiuj go ręcznie.</p>
      ) : null}
    </section>
  );
}
