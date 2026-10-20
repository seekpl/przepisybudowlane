import type { Metadata } from "next";
import Link from "next/link";

import { StatusBadge, TextTypeBadge } from "@/components/ds/Badges";
import { api } from "@/lib/api";
import { shortDate, typo } from "@/lib/format";

export const metadata: Metadata = { title: "Akty" };

export default async function Page() {
  const acts = await api.acts();
  return (
    <>
      <div className="pb-page-head">
        <h1 className="ui-display">Akty w serwisie</h1>
        <p className="ui-body">
          {typo(
            "Manifest aktów pierwszego wydania: ustawy i rozporządzenia, które odpowiadają na większość pytań inwestora i organu. Manifest czeka na zatwierdzenie przez prawnika.",
          )}
        </p>
      </div>
      <ul className="pb-list">
        {acts.map((a) => (
          <li key={a.slug} className="pb-list-item">
            <p className="ui-label pb-muted">{a.area}</p>
            <h2 className="ui-heading">
              <Link href={`/akty/${a.slug}`}>{a.short_title}</Link>
            </h2>
            <p className="ui-small pb-measure">{a.title}</p>
            <div className="pb-badges">
              <StatusBadge status={a.freshness.status} date={a.freshness.date} effectiveDate={a.freshness.effective_date} />
              {a.current_text ? <TextTypeBadge type={a.current_text.text_type} /> : null}
            </div>
            <p className="ui-small pb-muted">
              {a.current_text ? (
                <>
                  Tekst: <span className="meta-small">{a.current_text.journal}</span>
                  {a.current_text.legal_status_date ? (
                    <>
                      , stan na <span className="meta-small">{shortDate(a.current_text.legal_status_date)}</span>
                    </>
                  ) : null}
                </>
              ) : (
                "Tekstu jeszcze nie pobraliśmy — uruchom synchronizację z ELI."
              )}
              {" · "}ELI <span className="meta-small">{a.eli}</span>
            </p>
          </li>
        ))}
      </ul>
    </>
  );
}
