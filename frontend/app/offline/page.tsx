import type { Metadata } from "next";

import { Icon } from "@/components/ds/Icon";

export const metadata: Metadata = { title: "Brak połączenia" };

/** Bez sieci nie pokazujemy zapamiętanego tekstu prawa — mógłby być nieaktualny. */
export default function Page() {
  return (
    <div className="pb-stack-4" style={{ maxWidth: 640 }}>
      <h1 className="ui-display" style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
        <Icon name="wifi-off" size={28} />
        Brak połączenia
      </h1>
      <p className="ui-body">
        Nie możemy teraz sprawdzić, czy przepisy są aktualne, więc ich nie pokazujemy. Połącz się z internetem i odśwież
        stronę.
      </p>
    </div>
  );
}
