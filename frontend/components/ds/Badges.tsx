import { shortDate } from "@/lib/format";
import type { FreshnessStatus, TextType } from "@/lib/types";

import { Icon, type IconName } from "./Icon";

const TYPES: Record<TextType, { icon: IconName; label: string; hint: string }> = {
  ogloszony: { icon: "file-text", label: "Tekst ogłoszony", hint: "Brzmienie z Dziennika Ustaw" },
  jednolity: { icon: "book-check", label: "Tekst jednolity", hint: "Obwieszczenie z tekstem jednolitym" },
  kompilacja: { icon: "file-pen", label: "Własna kompilacja", hint: "Zmiany naniesione przez nas — tekst nieurzędowy" },
  nierozpoznany: { icon: "file-question", label: "Typ nierozpoznany", hint: "Nie ustaliliśmy, czym jest ten tekst" },
};

/** Typ tekstu: ikona + etykieta + obrys. Nieznana wartość to zawsze „Typ nierozpoznany”, nigdy „Tekst jednolity”. */
export function TextTypeBadge({ type }: { type: TextType | null | undefined }) {
  const key: TextType = type && type in TYPES ? type : "nierozpoznany";
  const t = TYPES[key];
  return (
    <span className={`pb-badge pb-type-${key}`} title={t.hint}>
      <Icon name={t.icon} />
      <span className="ui-label">{t.label}</span>
    </span>
  );
}

export function textTypeLabel(type: TextType | null | undefined): string {
  return TYPES[type && type in TYPES ? type : "nierozpoznany"].label;
}

const STATUS: Record<FreshnessStatus, { icon: IconName; label: (date?: string, eff?: string) => string }> = {
  potwierdzona: { icon: "circle-check", label: (d) => `Aktualność potwierdzona${d ? ` ${d}` : ""}` },
  zmiana: { icon: "calendar-clock", label: (_d, e) => `Zmiana od ${e ?? "—"}` },
  przejsciowa: { icon: "hourglass", label: (d) => `Utracił moc${d ? ` ${d}` : ""} · stosowany przejściowo` },
  niepotwierdzona: { icon: "triangle-alert", label: () => "Nie potwierdzono aktualności" },
  zawieszona: { icon: "octagon-pause", label: () => "Treść zawieszona" },
};

/** Status aktualności: od spokojnego do alarmowego. Brak lub błędna wartość = „Nie potwierdzono”. */
export function StatusBadge({
  status,
  date,
  effectiveDate,
}: {
  status: FreshnessStatus | null | undefined;
  date?: string | null;
  effectiveDate?: string | null;
}) {
  const key: FreshnessStatus = status && status in STATUS ? status : "niepotwierdzona";
  const s = STATUS[key];
  return (
    <span className={`pb-badge pb-status-${key}`}>
      <Icon name={s.icon} />
      <span className="ui-label">{s.label(shortDate(date), shortDate(effectiveDate))}</span>
    </span>
  );
}

export function statusLabel(status: FreshnessStatus, date?: string | null, effectiveDate?: string | null): string {
  return STATUS[status].label(shortDate(date), shortDate(effectiveDate));
}
