import type { Metadata } from "next";
import Link from "next/link";

import { Icon } from "@/components/ds/Icon";
import { api } from "@/lib/api";
import { plural, typo } from "@/lib/format";

export const metadata: Metadata = { title: "Krok po kroku" };

export default async function Page() {
  const guides = await api.guides();
  return (
    <>
      <div className="pb-page-head">
        <h1 className="ui-display">Krok po kroku</h1>
        <p className="ui-body">{typo("Co zrobić, w jakiej kolejności, jakie dokumenty przygotować i do którego urzędu pójść.")}</p>
      </div>
      <ul className="pb-grid pb-grid-3 pb-plain-list">
        {guides.map((g) => (
          <li key={g.slug}>
            <Link href={g.url} className="pb-tile">
              <span className="pb-tile-title ui-heading">{g.title}</span>
              <span className="ui-body">{typo(g.summary)}</span>
              <span className="pb-tile-more ui-small">
                {g.steps_count} {plural(g.steps_count, "krok", "kroki", "kroków")} <Icon name="arrow-right" />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
