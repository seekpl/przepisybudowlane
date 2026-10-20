"use client";

import { useActionState, useId, useState } from "react";

import { type ReportState, submitReport } from "@/app/actions";
import { Icon } from "@/components/ds/Icon";
import type { Mode } from "@/lib/types";

/** „Zgłoś błąd” przy każdej karcie: e-mail opcjonalny i tylko ze zgodą (RODO), termin obsługi w odpowiedzi. */
export function ErrorReportForm({
  mode,
  targetPath,
  targetLabel,
  unitSlug,
}: {
  mode: Mode;
  targetPath: string;
  targetLabel: string;
  unitSlug?: string;
}) {
  const [state, action, pending] = useActionState<ReportState, FormData>(submitReport, { status: "idle" });
  const [email, setEmail] = useState("");
  const id = useId();
  if (state.status === "ok") {
    return (
      <div role="status" className="pb-success ui-body">
        <Icon name="circle-check" size={20} />
        <p>{state.message}</p>
      </div>
    );
  }
  return (
    <form action={action} noValidate>
      <input type="hidden" name="target_path" value={targetPath} />
      <input type="hidden" name="target_label" value={targetLabel} />
      {unitSlug ? <input type="hidden" name="unit_slug" value={unitSlug} /> : null}
      <div className="pb-field">
        <label htmlFor={`${id}-msg`} className="ui-label">
          Co jest nie tak?
        </label>
        <textarea
          id={`${id}-msg`}
          name="message"
          className="pb-textarea ui-body"
          required
          minLength={5}
          maxLength={5000}
          defaultValue={state.fields?.message}
          aria-describedby={state.status === "error" ? `${id}-err` : undefined}
        />
      </div>
      <div className="pb-field">
        <label htmlFor={`${id}-email`} className="ui-label">
          Adres e-mail (opcjonalnie)
        </label>
        <input
          id={`${id}-email`}
          name="email"
          type="email"
          className="pb-input ui-body"
          autoComplete="email"
          defaultValue={state.fields?.email}
          onChange={(e) => setEmail(e.target.value)}
          aria-describedby={`${id}-email-hint`}
        />
        <p id={`${id}-email-hint`} className="ui-small pb-hint">
          Podaj go tylko, jeśli chcesz dostać odpowiedź. Usuniemy go po zamknięciu zgłoszenia.
        </p>
      </div>
      {email || state.fields?.email ? (
        <div className="pb-field">
          <label className="pb-check ui-small">
            <input type="checkbox" name="consent" />
            <span>Zgadzam się na użycie adresu wyłącznie do odpowiedzi na to zgłoszenie.</span>
          </label>
        </div>
      ) : null}
      {state.status === "error" ? (
        <p id={`${id}-err`} className="pb-field-error ui-body" role="alert" style={{ marginTop: "var(--space-3)" }}>
          <Icon name="triangle-alert" />
          {state.message}
        </p>
      ) : null}
      <div style={{ marginTop: "var(--space-4)" }}>
        <button type="submit" className={`pb-btn pb-btn-secondary pb-${mode}`} disabled={pending}>
          <Icon name="flag" />
          <span>{pending ? "Wysyłamy…" : "Wyślij zgłoszenie"}</span>
        </button>
      </div>
    </form>
  );
}
