// Formatowanie według identyfikacji: daty d.mm.rrrr w odznakach i metryce, słownie w zdaniach.

const MONTHS = [
  "stycznia",
  "lutego",
  "marca",
  "kwietnia",
  "maja",
  "czerwca",
  "lipca",
  "sierpnia",
  "września",
  "października",
  "listopada",
  "grudnia",
];

export const NBSP = " ";

function parts(iso: string): [number, number, number] {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return [y ?? 0, m ?? 1, d ?? 1];
}

/** „2026-09-20” → „20.09.2026”. */
export function shortDate(iso: string | null | undefined): string | undefined {
  if (!iso) return undefined;
  const [y, m, d] = parts(iso);
  return `${d}.${String(m).padStart(2, "0")}.${y}`;
}

/** „2026-09-20” → „20 września 2026 r.” (ze spacjami niełamiącymi). */
export function wordsDate(iso: string | null | undefined): string | undefined {
  if (!iso) return undefined;
  const [y, m, d] = parts(iso);
  return `${d}${NBSP}${MONTHS[m - 1]} ${y}${NBSP}r.`;
}

/** Data i godzina w strefie Polski: „20.10.2026, 10:00”. */
export function dateTime(iso: string | null | undefined): string | undefined {
  if (!iso) return undefined;
  const dt = new Date(iso);
  const f = new Intl.DateTimeFormat("pl-PL", {
    timeZone: "Europe/Warsaw",
    day: "numeric",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return f.format(dt);
}

/**
 * Spacje niełamiące w treściach interfejsu i objaśnień: po jednoliterowych wyrazach, po skrótach
 * jednostek redakcyjnych i między liczbą a jednostką. Tekstu prawa tą funkcją nie przetwarzamy.
 */
export function typo(text: string): string {
  return text
    .replace(/(^|[\s(„])([aiouwzAIOUWZ])\s+/g, `$1$2${NBSP}`)
    .replace(/\b(art\.|ust\.|pkt|lit\.|poz\.|nr|§)\s+(?=\d)/g, `$1${NBSP}`)
    .replace(/(\d)\s+(m²|m|km|cm|mm|dni|r\.|%)(?=[\s.,;:)]|$)/g, `$1${NBSP}$2`)
    .replace(/(\d)\s+(?=\d{3}\b)/g, `$1${NBSP}`);
}

export function plural(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return few;
  return many;
}
