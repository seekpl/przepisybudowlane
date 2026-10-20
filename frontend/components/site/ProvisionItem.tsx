import Link from "next/link";

import { StatusBadge, TextTypeBadge } from "@/components/ds/Badges";
import type { ProvisionSummary } from "@/lib/types";

export function ProvisionItem({ p }: { p: ProvisionSummary }) {
  return (
    <li className="pb-list-item">
      <p className="meta-small pb-list-meta">{p.display_label}</p>
      <h3 className="ui-heading">
        <Link href={p.url}>{p.title ?? p.display_label}</Link>
      </h3>
      <div className="pb-badges">
        <StatusBadge status={p.freshness.status} date={p.freshness.date} effectiveDate={p.freshness.effective_date} />
        <TextTypeBadge type={p.text_type} />
      </div>
      <p className="ui-small pb-muted">
        {p.act.short_title}
        {p.has_explanation ? " · z objaśnieniem prostym językiem" : ""}
      </p>
    </li>
  );
}
