"use client";

import { Button } from "@/components/ds/Button";

/** Gdy API nie odpowiada, nie pokazujemy niczego, co mogłoby udawać aktualny przepis. */
export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="pb-stack-4" style={{ maxWidth: 640 }}>
      <h1 className="ui-display">Nie możemy teraz pobrać danych</h1>
      <p className="ui-body">
        Serwer z przepisami nie odpowiada. Nie pokazujemy zapamiętanych treści, bo mogłyby być nieaktualne. Spróbuj za
        chwilę.
      </p>
      <div>
        <Button onClick={reset} icon="history">
          Spróbuj ponownie
        </Button>
      </div>
    </div>
  );
}
