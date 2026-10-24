"use client";

import { useActionState } from "react";

import {
  type EditorState,
  editorCloseAlarm,
  editorCloseTask,
  editorDecideAiDraft,
  editorDecideText,
  editorLogin,
  editorTransition,
  editorTransitional,
  editorAddSynonym,
  editorRequestAiDraft,
} from "@/app/actions";
import { Icon } from "@/components/ds/Icon";

// Ukryte pola nie mogą się nazywać „id” ani jak inne właściwości formularza: input name="id" przesłania
// form.id, a React dołącza wartość klikniętego przycisku (decision) przez atrybut form={form.id} — przycisk
// „Zatwierdź” wysyłał wtedy formularz bez decyzji, czyli jak „Odrzuć”.
function Feedback({ state }: { state: EditorState }) {
  if (state.error)
    return (
      <p className="pb-field-error ui-small" role="alert">
        <Icon name="triangle-alert" />
        {state.error}
      </p>
    );
  if (state.ok)
    return (
      <p className="pb-success ui-small" role="status">
        <Icon name="check" />
        {state.ok}
      </p>
    );
  return null;
}

export function LoginForm() {
  const [state, action, pending] = useActionState<EditorState, FormData>(editorLogin, {});
  return (
    <form action={action} className="pb-panel" style={{ maxWidth: 480 }}>
      <div className="pb-field">
        <label htmlFor="token" className="ui-label">
          Token redakcji
        </label>
        <input id="token" name="token" type="password" className="pb-input ui-body" autoComplete="current-password" required />
        <p className="ui-small pb-hint">Tymczasowo, do czasu logowania przez OIDC. Token dostajesz od operatora usługi.</p>
      </div>
      <Feedback state={state} />
      <div style={{ marginTop: "var(--space-4)" }}>
        <button type="submit" className="pb-btn pb-btn-primary pb-expert" disabled={pending}>
          <Icon name="log-in" />
          <span>Zaloguj się</span>
        </button>
      </div>
    </form>
  );
}

const NEXT: Record<string, { to: string; label: string; needsComment?: boolean }[]> = {
  szkic: [{ to: "recenzja", label: "Przekaż do recenzji" }],
  recenzja: [
    { to: "zatwierdzony", label: "Zatwierdź" },
    { to: "szkic", label: "Zwróć do poprawy" },
  ],
  zatwierdzony: [{ to: "opublikowany", label: "Opublikuj" }],
  opublikowany: [
    { to: "zawieszony", label: "Zawieś", needsComment: true },
    { to: "cofniety", label: "Cofnij", needsComment: true },
  ],
  zawieszony: [
    { to: "opublikowany", label: "Przywróć po sprawdzeniu" },
    { to: "cofniety", label: "Cofnij", needsComment: true },
  ],
  cofniety: [],
};

export function TransitionForm({ entity, id, state }: { entity: string; id: number; state: string }) {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorTransition, {});
  const options = NEXT[state] ?? [];
  if (options.length === 0) return <span className="ui-small pb-muted">Brak dalszych kroków</span>;
  return (
    <form action={action} className="pb-stack-2">
      <input type="hidden" name="entity" value={entity} />
      <input type="hidden" name="item_id" value={id} />
      <label className="pb-sr" htmlFor={`c-${entity}-${id}`}>
        Komentarz
      </label>
      <input
        id={`c-${entity}-${id}`}
        name="comment"
        className="pb-input ui-small"
        placeholder={options.some((o) => o.needsComment) ? "Powód (wymagany przy zawieszeniu i cofnięciu)" : "Komentarz (opcjonalnie)"}
      />
      <div className="pb-link-row">
        {options.map((o) => (
          <button key={o.to} type="submit" name="to_state" value={o.to} className="pb-btn pb-btn-secondary pb-expert" disabled={pending}>
            <span>{o.label}</span>
          </button>
        ))}
      </div>
      <Feedback state={res} />
    </form>
  );
}

export function CloseTaskForm({ id }: { id: number }) {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorCloseTask, {});
  return (
    <form action={action} className="pb-stack-2">
      <input type="hidden" name="item_id" value={id} />
      <label className="pb-sr" htmlFor={`r-${id}`}>
        Rozwiązanie
      </label>
      <input id={`r-${id}`} name="resolution" className="pb-input ui-small" placeholder="Jak rozwiązano zadanie" />
      <button type="submit" className="pb-btn pb-btn-secondary pb-expert" disabled={pending}>
        <Icon name="check" />
        <span>Zamknij zadanie</span>
      </button>
      <Feedback state={res} />
    </form>
  );
}

export function TextDecisionForm({ id }: { id: number }) {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorDecideText, {});
  return (
    <form action={action} className="pb-stack-2">
      <input type="hidden" name="item_id" value={id} />
      <label className="pb-sr" htmlFor={`t-${id}`}>
        Uzasadnienie
      </label>
      <input id={`t-${id}`} name="comment" className="pb-input ui-small" placeholder="Uzasadnienie decyzji" />
      <div className="pb-link-row">
        <button type="submit" name="decision" value="akceptuj" className="pb-btn pb-btn-secondary pb-expert" disabled={pending}>
          <span>Zaakceptuj tekst</span>
        </button>
        <button type="submit" name="decision" value="odrzuc" className="pb-btn pb-btn-quiet pb-expert" disabled={pending}>
          <span>Odrzuć</span>
        </button>
      </div>
      <Feedback state={res} />
    </form>
  );
}

export function AiDraftDecisionForm({ id }: { id: number }) {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorDecideAiDraft, {});
  return (
    <form action={action} className="pb-stack-2">
      <input type="hidden" name="item_id" value={id} />
      <label className="ui-label" htmlFor={`ai-${id}`}>
        Co sprawdzono
      </label>
      <input id={`ai-${id}`} name="comment" className="pb-input ui-small" placeholder="np. zgodne z nowym brzmieniem pkt 1a" />
      <div className="pb-link-row">
        <button type="submit" name="decision" value="zatwierdz" className="pb-btn pb-btn-secondary pb-expert" disabled={pending}>
          <Icon name="check" />
          <span>Zatwierdź i opublikuj</span>
        </button>
        <button type="submit" name="decision" value="odrzuc" className="pb-btn pb-btn-quiet pb-expert" disabled={pending}>
          <span>Odrzuć szkic</span>
        </button>
      </div>
      <Feedback state={res} />
    </form>
  );
}

export function AiDraftRequestForm() {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorRequestAiDraft, {});
  return (
    <form action={action} className="pb-stack-2">
      <label className="ui-label" htmlFor="ai-unit">
        Adres karty przepisu
      </label>
      <input id="ai-unit" name="unit" className="pb-input ui-small" placeholder="/przepis/prawo-budowlane-art-29-ust-1-pkt-2" />
      <button type="submit" className="pb-btn pb-btn-quiet pb-expert" disabled={pending}>
        <span>Zleć szkic AI</span>
      </button>
      <Feedback state={res} />
    </form>
  );
}

export function CloseAlarmForm({ id }: { id: number }) {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorCloseAlarm, {});
  return (
    <form action={action} className="pb-stack-2">
      <input type="hidden" name="item_id" value={id} />
      <label className="ui-label" htmlFor={`a-${id}`}>
        Co sprawdzono
      </label>
      <input id={`a-${id}`} name="resolution" className="pb-input ui-small" placeholder="np. poprawiono słownik powiązań w wydaniu 1.4" />
      <button type="submit" className="pb-btn pb-btn-secondary pb-expert" disabled={pending}>
        <Icon name="check" />
        <span>Zamknij alarm i wznów synchronizację</span>
      </button>
      <Feedback state={res} />
    </form>
  );
}

export function TransitionalForm({ taskId, actSlug, since, basis }: { taskId: number; actSlug: string; since: string | null; basis: string }) {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorTransitional, {});
  const id = (name: string) => `pp-${taskId}-${name}`;
  return (
    <form action={action} className="pb-stack-2">
      <input type="hidden" name="task_id" value={taskId} />
      <input type="hidden" name="act_slug" value={actSlug} />
      <div className="pb-field">
        <label className="ui-label" htmlFor={id("from")}>
          Stosuje się przejściowo od
        </label>
        <input id={id("from")} name="valid_from" type="date" className="pb-input ui-small" defaultValue={since ?? ""} required />
      </div>
      <div className="pb-field">
        <label className="ui-label" htmlFor={id("to")}>
          Do (jeśli przepis podaje termin)
        </label>
        <input id={id("to")} name="valid_to" type="date" className="pb-input ui-small" />
      </div>
      <div className="pb-field">
        <label className="ui-label" htmlFor={id("basis")}>
          Podstawa — przepis przejściowy
        </label>
        <input id={id("basis")} name="basis" className="pb-input ui-small" defaultValue={basis} required />
      </div>
      <div className="pb-field">
        <label className="ui-label" htmlFor={id("desc")}>
          Do jakich spraw stosuje się akt dalej
        </label>
        <textarea id={id("desc")} name="description" className="pb-input ui-small" rows={3} required />
      </div>
      <button type="submit" className="pb-btn pb-btn-secondary pb-expert" disabled={pending}>
        <Icon name="check" />
        <span>Zapisz stosowanie przejściowe</span>
      </button>
      <Feedback state={res} />
    </form>
  );
}

export function SynonymForm({ missId, term, suggestions }: { missId: number; term: string; suggestions: string[] }) {
  const [res, action, pending] = useActionState<EditorState, FormData>(editorAddSynonym, {});
  return (
    <form action={action} className="pb-stack-2">
      <input type="hidden" name="miss_id" value={missId} />
      <input type="hidden" name="term" value={term} />
      <label className="ui-label" htmlFor={`syn-${missId}`}>
        Szukaj też (oddziel przecinkami)
      </label>
      <input id={`syn-${missId}`} name="expansions" className="pb-input ui-small" defaultValue={suggestions.join(", ")} />
      <button type="submit" className="pb-btn pb-btn-secondary pb-expert" disabled={pending}>
        <Icon name="check" />
        <span>Dodaj synonim</span>
      </button>
      <Feedback state={res} />
    </form>
  );
}
