import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import type { Mode } from "@/lib/types";

import { Icon, type IconName } from "./Icon";

type Variant = "primary" | "secondary" | "quiet";

interface Common {
  variant?: Variant;
  mode?: Mode;
  icon?: IconName;
  iconAfter?: IconName;
  children: ReactNode;
  className?: string;
}

function classes(variant: Variant, mode: Mode, className?: string): string {
  return ["pb-btn", `pb-btn-${variant}`, `pb-${mode}`, className].filter(Boolean).join(" ");
}

function Content({ icon, iconAfter, children }: Pick<Common, "icon" | "iconAfter" | "children">) {
  return (
    <>
      {icon ? <Icon name={icon} /> : null}
      <span>{children}</span>
      {iconAfter ? <Icon name={iconAfter} /> : null}
    </>
  );
}

/** Przycisk: jeden `primary` na ekran; czasownik w etykiecie; bez wersalików i wykrzykników. */
export function Button({
  variant = "primary",
  mode = "simple",
  icon,
  iconAfter,
  children,
  className,
  type = "button",
  ...rest
}: Common & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type={type} className={classes(variant, mode, className)} {...rest}>
      <Content icon={icon} iconAfter={iconAfter}>
        {children}
      </Content>
    </button>
  );
}

/** Link wyglądający jak przycisk — do nawigacji, nie do akcji. */
export function ButtonLink({
  href,
  variant = "primary",
  mode = "simple",
  icon,
  iconAfter,
  children,
  className,
  external,
}: Common & { href: string; external?: boolean }) {
  if (external) {
    return (
      <a href={href} className={classes(variant, mode, className)} target="_blank" rel="noopener">
        <Content icon={icon} iconAfter={iconAfter}>
          {children}
        </Content>
        <span className="pb-sr"> (otwiera się w nowej karcie)</span>
      </a>
    );
  }
  return (
    <Link href={href} className={classes(variant, mode, className)}>
      <Content icon={icon} iconAfter={iconAfter}>
        {children}
      </Content>
    </Link>
  );
}
