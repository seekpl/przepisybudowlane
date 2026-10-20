import Link from "next/link";

import type { Mode } from "@/lib/types";

import { MobileMenu } from "./MobileMenu";
import { ModeSwitch } from "./ModeSwitch";
import { NavLinks } from "./NavLinks";

export function SiteHeader({ mode }: { mode: Mode }) {
  return (
    <header className="pb-header">
      <div className="pb-wrap pb-header-row">
        <Link href="/" className="pb-brand" aria-label="Przepisy budowlane — strona główna">
          {/* Komputer: logo poziome; telefon: sam znak + nazwa w ui-heading (identyfikacja, „Znak i logo”). */}
          <picture className="pb-brand-full">
            <source srcSet="/brand/logo-poziome-odwrocony.svg" media="(prefers-color-scheme: dark)" />
            <img src="/brand/logo-poziome-kolor.svg" alt="" width={216} height={48} />
          </picture>
          <span className="pb-brand-compact">
            {/* eslint-disable-next-line @next/next/no-img-element -- znak SVG; next/image nie optymalizuje SVG */}
            <img src="/brand/znak-kolor.svg" alt="" width={40} height={40} className="pb-brand-mark" />
            <span className="ui-heading">Przepisy budowlane</span>
          </span>
        </Link>
        <div className="pb-desktop-only">
          <ModeSwitch mode={mode} />
        </div>
        <MobileMenu>
          <NavLinks id="nawigacja-mobilna" />
          <ModeSwitch mode={mode} id="tryb-mobilny" />
        </MobileMenu>
      </div>
      <div className="pb-nav-row pb-desktop-only">
        <div className="pb-wrap">
          <NavLinks />
        </div>
      </div>
    </header>
  );
}
