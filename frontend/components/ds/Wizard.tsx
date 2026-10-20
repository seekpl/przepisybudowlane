"use client";

import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { shortDate, typo } from "@/lib/format";
import type { Mode, Tree, TreeNode } from "@/lib/types";

import { StatusBadge } from "./Badges";
import { Button, ButtonLink } from "./Button";
import { FreshnessNotice } from "./FreshnessNotice";
import { Icon } from "./Icon";

interface Answer {
  node: string;
  choice: number;
}

/** Etykiety kroków: przebyta ścieżka + przewidywany dalszy ciąg (pierwsza odpowiedź) + „Wynik”. */
function stepLabels(tree: Tree, path: Answer[], currentKey: string): string[] {
  const labels = path.map((a) => tree.nodes[a.node]?.step_label ?? "");
  let key: string | undefined = currentKey;
  const seen = new Set<string>();
  while (key && !seen.has(key)) {
    seen.add(key);
    const node: TreeNode | undefined = tree.nodes[key];
    if (!node) break;
    if (node.kind === "wynik") {
      labels.push("Wynik");
      break;
    }
    labels.push(node.step_label);
    key = node.options[0]?.next;
  }
  return labels;
}

function Stepper({ labels, current }: { labels: string[]; current: number }) {
  return (
    <nav className="pb-steps" aria-label="Postęp">
      <p className="pb-steps-count ui-small">
        Krok {current} z {labels.length}
      </p>
      <ol>
        {labels.map((label, i) => {
          const n = i + 1;
          const state = n < current ? "done" : n === current ? "current" : "todo";
          return (
            <li key={i} className={`pb-step pb-step-${state}`} aria-current={state === "current" ? "step" : undefined}>
              <span className="pb-step-dot" aria-hidden="true">
                {state === "done" ? <Icon name="check" size={14} /> : n}
              </span>
              <span className="ui-small">
                {label}
                {state === "done" ? <span className="pb-sr"> (zrobione)</span> : null}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Result({
  node,
  mode,
  tree,
  focus,
  onBack,
  onRestart,
}: {
  node: TreeNode;
  mode: Mode;
  tree: Tree;
  focus: boolean;
  onBack: () => void;
  onRestart: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focus) heading.current?.focus();
  }, [focus]);
  const firstUnit = node.units[0];
  return (
    <section className="pb-result" aria-labelledby="wynik-tytul">
      <p className="pb-result-kicker ui-label">
        <Icon name="scale" />
        Wynik
      </p>
      {node.suspended ? (
        <>
          <h2 id="wynik-tytul" className="ui-title" tabIndex={-1} ref={heading}>
            Ta odpowiedź czeka na ponowne sprawdzenie
          </h2>
          <FreshnessNotice status="niepotwierdzona" mode={mode} title="Przepis, na którym opiera się wynik, zmienił się">
            <p className={mode === "simple" ? "ui-body" : "ui-small"}>
              {typo(node.suspended_reason ?? "")} Do czasu weryfikacji skorzystaj z oficjalnego tekstu przepisu.
            </p>
          </FreshnessNotice>
        </>
      ) : (
        <>
          <h2 id="wynik-tytul" className="ui-title" tabIndex={-1} ref={heading}>
            {typo(node.result_title ?? "")}
          </h2>
          <p className="ui-body pb-measure">{typo(node.result_body ?? "")}</p>
        </>
      )}
      {node.basis ? (
        <div className="pb-result-basis">
          <p className="ui-label">Podstawa prawna</p>
          <p className="meta">{node.basis}</p>
          {node.status ? (
            <StatusBadge status={node.status} date={node.status_date} effectiveDate={node.status_effective_date} />
          ) : null}
          {node.units.length > 0 ? (
            <ul className="pb-plain-list ui-small">
              {node.units.map((u) => (
                <li key={u.slug}>
                  <Link href={u.url}>
                    {u.display_label}
                    {u.title ? ` — ${u.title}` : ""}
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      {tree.is_demo ? (
        <p className="ui-small pb-demo-label">
          {typo("Kreator demonstracyjny — nie przeszedł recenzji prawnej. Informacja, nie porada prawna; nie odpowiadamy na pytania o konkretną sprawę.")}
        </p>
      ) : (
        <p className="ui-small pb-muted">
          {typo(`Zweryfikowano ${shortDate(tree.verified_on)}. Informacja, nie porada prawna; w sprawie konkretnej działki zapytaj w starostwie.`)}
        </p>
      )}
      {node.links.length > 0 ? (
        <div className="pb-link-row">
          {node.links.map((l) => (
            <ButtonLink key={l.url} href={l.url} external variant="secondary" mode={mode} icon="external-link">
              {l.label}
            </ButtonLink>
          ))}
        </div>
      ) : null}
      <div className="pb-actions">
        <Button variant="secondary" mode={mode} icon="arrow-left" onClick={onBack}>
          Zmień odpowiedzi
        </Button>
        {firstUnit ? (
          <ButtonLink href={firstUnit.url} variant="primary" mode={mode} iconAfter="arrow-right">
            Zobacz przepis
          </ButtonLink>
        ) : (
          <Button variant="quiet" mode={mode} onClick={onRestart}>
            Zacznij od nowa
          </Button>
        )}
      </div>
      {firstUnit ? (
        <p>
          <Button variant="quiet" mode={mode} onClick={onRestart}>
            Zacznij od nowa
          </Button>
        </p>
      ) : null}
    </section>
  );
}

function Question({
  node,
  mode,
  initial,
  focus,
  canGoBack,
  onBack,
  onNext,
}: {
  node: TreeNode;
  mode: Mode;
  initial: number | null;
  focus: boolean;
  canGoBack: boolean;
  onBack: () => void;
  onNext: (choice: number) => void;
}) {
  const [selected, setSelected] = useState<number | null>(initial);
  const [error, setError] = useState(false);
  const uid = useId();
  const legend = useRef<HTMLLegendElement>(null);
  // Fokus przenosimy dopiero po działaniu użytkownika — nie przy wejściu na stronę.
  useEffect(() => {
    if (focus) legend.current?.focus();
  }, [focus, node.key]);
  const name = `q-${node.key}`;
  const errId = `${uid}-err`;
  const helpId = `${uid}-help`;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (selected === null) setError(true);
        else onNext(selected);
      }}
      noValidate
    >
      <fieldset
        className="pb-question"
        aria-describedby={[node.help ? helpId : null, error ? errId : null].filter(Boolean).join(" ") || undefined}
      >
        <legend className={mode === "simple" ? "ui-display" : "ui-title"} tabIndex={-1} ref={legend}>
          {typo(node.question ?? "")}
        </legend>
        {node.help ? (
          <p id={helpId} className="ui-body pb-muted">
            {typo(node.help)}
          </p>
        ) : null}
        <div className="pb-options">
          {node.options.map((o, i) => {
            const id = `${name}-${i}`;
            return (
              <label key={id} htmlFor={id} className={`pb-option${selected === i ? " is-selected" : ""}`}>
                <input
                  type="radio"
                  id={id}
                  name={name}
                  checked={selected === i}
                  onChange={() => {
                    setSelected(i);
                    setError(false);
                  }}
                />
                <span className="ui-body">{typo(o.label)}</span>
              </label>
            );
          })}
        </div>
        {error ? (
          <p id={errId} className="pb-field-error ui-body" role="alert">
            <Icon name="triangle-alert" />
            Wybierz jedną odpowiedź, żeby przejść dalej.
          </p>
        ) : null}
        <div className="pb-actions">
          {canGoBack ? (
            <Button variant="secondary" mode={mode} icon="arrow-left" onClick={onBack}>
              Wstecz
            </Button>
          ) : (
            <span />
          )}
          <Button type="submit" variant="primary" mode={mode} iconAfter="arrow-right">
            Dalej
          </Button>
        </div>
      </fieldset>
    </form>
  );
}

/**
 * Kreator („Czy potrzebuję pozwolenia?”): wersjonowane drzewko z API. Odpowiedzi zapisujemy lokalnie,
 * żeby odświeżenie strony ich nie kasowało (klucz zawiera wersję drzewka — po zmianie treści start od nowa).
 */
export function Wizard({ tree, mode }: { tree: Tree; mode: Mode }) {
  const storageKey = `pb-kreator:${tree.slug}:v${tree.version_id}`;
  const [path, setPath] = useState<Answer[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [back, setBack] = useState<Record<string, number>>({});
  const [moved, setMoved] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const saved = JSON.parse(raw) as Answer[];
        // Odtwarzamy tylko ścieżkę zgodną z bieżącą wersją drzewka.
        const valid: Answer[] = [];
        let key = tree.root;
        for (const a of saved) {
          const node = tree.nodes[key];
          const opt = node?.options[a.choice];
          if (!node || a.node !== key || !opt) break;
          valid.push(a);
          key = opt.next;
        }
        setPath(valid);
      }
    } catch {
      /* brak dostępu do pamięci przeglądarki — kreator działa bez zapisu */
    }
    setLoaded(true);
  }, [storageKey, tree]);

  useEffect(() => {
    if (!loaded) return;
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(path));
    } catch {
      /* jw. */
    }
  }, [path, loaded, storageKey]);

  const currentKey = useMemo(() => {
    let key = tree.root;
    for (const a of path) key = tree.nodes[a.node]?.options[a.choice]?.next ?? key;
    return key;
  }, [path, tree]);
  const node = tree.nodes[currentKey];
  const labels = stepLabels(tree, path, currentKey);

  if (!node) return <p className="ui-body">Ten kreator jest niekompletny. Zgłoś błąd, a poprawimy go.</p>;

  return (
    <div className={`pb-wizard pb-${mode}`}>
      <Stepper labels={labels} current={path.length + 1} />
      {node.kind === "wynik" ? (
        <Result
          node={node}
          mode={mode}
          tree={tree}
          focus={moved}
          onBack={() => {
            // Wracamy na początek z zaznaczonymi poprzednimi odpowiedziami.
            setBack(Object.fromEntries(path.map((a) => [a.node, a.choice])));
            setMoved(true);
            setPath([]);
          }}
          onRestart={() => {
            setBack({});
            setMoved(true);
            setPath([]);
          }}
        />
      ) : (
        <Question
          key={node.key}
          node={node}
          mode={mode}
          initial={back[node.key] ?? null}
          focus={moved}
          canGoBack={path.length > 0}
          onBack={() => {
            const last = path[path.length - 1];
            if (last) setBack((b) => ({ ...b, [last.node]: last.choice }));
            setMoved(true);
            setPath(path.slice(0, -1));
          }}
          onNext={(choice) => {
            setBack((b) => ({ ...b, [node.key]: choice }));
            setMoved(true);
            setPath([...path, { node: node.key, choice }]);
          }}
        />
      )}
    </div>
  );
}
