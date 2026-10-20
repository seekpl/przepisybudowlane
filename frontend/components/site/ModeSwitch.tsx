import { setMode } from "@/app/actions";
import type { Mode } from "@/lib/types";

/**
 * Tryb prosty (inwestor) i ekspercki (urzędnik): te same dane, inna gęstość i kolejność treści.
 * Formularz z akcją serwera — działa także bez JavaScriptu.
 */
export function ModeSwitch({ mode, id = "tryb" }: { mode: Mode; id?: string }) {
  return (
    <form action={setMode} className="pb-mode">
      <span className="ui-small pb-muted" id={`${id}-etykieta`}>
        Tryb
      </span>
      <div className="pb-mode-group" role="group" aria-labelledby={`${id}-etykieta`}>
        <button type="submit" name="tryb" value="prosty" aria-pressed={mode === "simple"} className="ui-small">
          Prosty
        </button>
        <button type="submit" name="tryb" value="ekspert" aria-pressed={mode === "expert"} className="ui-small">
          Ekspercki
        </button>
      </div>
    </form>
  );
}
