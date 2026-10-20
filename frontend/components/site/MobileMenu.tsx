"use client";

import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useRef } from "react";

import { Icon } from "@/components/ds/Icon";

/** Menu na telefonie: <details> działa bez JavaScriptu; z JavaScriptem zamyka się po przejściu na inną stronę. */
export function MobileMenu({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const pathname = usePathname();
  useEffect(() => {
    if (ref.current) ref.current.open = false;
  }, [pathname]);
  return (
    <details className="pb-menu pb-mobile-only" ref={ref}>
      <summary aria-controls="nawigacja-mobilna">
        <span className="pb-menu-open">
          <Icon name="menu" size={20} />
          <span className="ui-body">Menu</span>
        </span>
        <span className="pb-menu-close">
          <Icon name="x" size={20} />
          <span className="ui-body">Zamknij</span>
        </span>
      </summary>
      <div className="pb-menu-panel">{children}</div>
    </details>
  );
}
