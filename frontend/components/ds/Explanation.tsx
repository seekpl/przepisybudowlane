import type { ReactNode } from "react";

import { typo } from "@/lib/format";
import type { Mode } from "@/lib/types";

import { Icon } from "./Icon";

/** Objaśnienie prostym językiem — zawsze z etykietą „Objaśnienie nieurzędowe”, nigdy stylizowane na przepis. */
export function Explanation({
  title,
  mode = "simple",
  children,
  footer,
}: {
  title?: string | null;
  mode?: Mode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <section className={`pb-explain pb-${mode}`} aria-label="Objaśnienie nieurzędowe">
      <p className="pb-explain-label ui-label">
        <Icon name="message-square-text" />
        Objaśnienie nieurzędowe
      </p>
      {title ? <p className={`pb-explain-title ${mode === "simple" ? "ui-heading" : "ui-body"}`}>{typo(title)}</p> : null}
      <div className={mode === "simple" ? "ui-body" : "ui-small"}>{children}</div>
      {footer ? <div className="pb-explain-footer ui-small">{footer}</div> : null}
    </section>
  );
}
