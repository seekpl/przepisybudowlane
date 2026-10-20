import { Icon } from "@/components/ds/Icon";
import type { Mode } from "@/lib/types";

export function SearchForm({ mode, defaultValue = "", label = "Czego szukasz?" }: { mode: Mode; defaultValue?: string; label?: string }) {
  return (
    <form action="/szukaj" method="get" role="search" className="pb-search">
      <label htmlFor="q" className={mode === "simple" ? "ui-heading" : "ui-label"}>
        {label}
      </label>
      <input
        id="q"
        name="q"
        type="search"
        className="pb-input ui-body"
        defaultValue={defaultValue}
        placeholder="np. odległość od granicy, płot, warunki zabudowy"
        autoComplete="off"
        enterKeyHint="search"
        required
        maxLength={200}
      />
      <button type="submit" className={`pb-btn pb-btn-primary pb-${mode}`}>
        <Icon name="search" />
        <span>Szukaj</span>
      </button>
    </form>
  );
}
