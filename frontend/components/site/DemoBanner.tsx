import Link from "next/link";

import { Icon } from "@/components/ds/Icon";

/** Prototyp mówi o sobie wprost — spokojnie, bez wykrzykników. */
export function DemoBanner() {
  return (
    <div className="pb-banner" role="note" aria-label="Wersja prototypowa">
      <div className="pb-wrap">
        <p className="ui-small">
          <Icon name="info" />
          <span>
            To prototyp. Objaśnienia, kreator i ścieżki są demonstracyjne i nie przeszły recenzji prawnej — nie opieraj
            na nich decyzji. <Link href="/o-serwisie">Jak działa serwis</Link>
          </span>
        </p>
      </div>
    </div>
  );
}
