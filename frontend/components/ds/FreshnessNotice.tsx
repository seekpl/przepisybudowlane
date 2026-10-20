import type { ReactNode } from "react";

import { typo } from "@/lib/format";
import type { FreshnessStatus, Mode, Notice } from "@/lib/types";

import { Icon, type IconName } from "./Icon";

const COPY: Record<Exclude<FreshnessStatus, "potwierdzona">, { icon: IconName; title: string; body: string }> = {
  zmiana: {
    icon: "calendar-clock",
    title: "Ten przepis wkrótce się zmieni",
    body: "Nowelizacja jest już opublikowana. Poniżej tekst, który obowiązuje dziś.",
  },
  przejsciowa: {
    icon: "hourglass",
    title: "Ten przepis utracił moc",
    body: "Stosuje się go już tylko przejściowo, na warunkach podanych w metryce. Sprawdź, czy dotyczą Twojej sprawy.",
  },
  niepotwierdzona: {
    icon: "triangle-alert",
    title: "Nie potwierdziliśmy, że ten tekst jest aktualny",
    body: "Zanim się na nim oprzesz, porównaj go z oficjalnym tekstem — link znajdziesz w metryce.",
  },
  zawieszona: {
    icon: "octagon-pause",
    title: "Treść tego przepisu jest zawieszona",
    body: "Przepisu nie stosuje się w okresie zawieszenia. Nie opieraj na nim decyzji — podstawę zawieszenia podajemy w metryce.",
  },
};

/** Komunikat o aktualności — zawsze przed tekstem przepisu, nigdy w stopce. Spokojny i rzeczowy. */
export function FreshnessNotice({
  status,
  title,
  mode = "simple",
  children,
}: {
  status: FreshnessStatus;
  title?: string;
  mode?: Mode;
  children?: ReactNode;
}) {
  if (status === "potwierdzona") return null;
  const copy = COPY[status];
  const heading = title ?? copy.title;
  return (
    <div className={`pb-notice pb-notice-${status} pb-${mode}`} role="note" aria-label={heading}>
      <Icon name={copy.icon} size={mode === "simple" ? 22 : 18} />
      <div>
        <p className={`pb-notice-title ${mode === "simple" ? "ui-heading" : "ui-label"}`}>{typo(heading)}</p>
        {children ?? <p className={mode === "simple" ? "ui-body" : "ui-small"}>{typo(copy.body)}</p>}
      </div>
    </div>
  );
}

/** Wszystkie komunikaty z API, od najpoważniejszego. */
export function FreshnessNotices({ notices, mode }: { notices: Notice[]; mode: Mode }) {
  if (notices.length === 0) return null;
  return (
    <div className="pb-notices">
      {notices.map((n) => (
        <FreshnessNotice key={n.code} status={n.status} title={n.title} mode={mode}>
          <p className={mode === "simple" ? "ui-body" : "ui-small"}>{typo(n.body)}</p>
        </FreshnessNotice>
      ))}
    </div>
  );
}
