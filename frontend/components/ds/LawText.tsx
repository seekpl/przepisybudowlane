import type { ReactNode } from "react";

import type { Mode, Paragraph } from "@/lib/types";

/** Oficjalne brzmienie — krój szeryfowy („to jest dokument”). Tekst bez zmian, skrótów i wyróżnień. */
export function LawText({ paragraphs, mode = "simple", children }: { paragraphs: Paragraph[]; mode?: Mode; children?: ReactNode }) {
  return (
    <div className={`pb-law pb-${mode}`} lang="pl">
      {paragraphs.map((p, i) => (
        <p key={i} className={mode === "simple" ? "law-simple" : "law-expert"}>
          {p.unit ? <span className="law-unit pb-law-unit">{p.unit} </span> : null}
          {p.text}
        </p>
      ))}
      {children}
    </div>
  );
}
