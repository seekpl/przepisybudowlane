"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Icon, type IconName } from "@/components/ds/Icon";

const LINKS: { href: string; label: string; icon: IconName }[] = [
  { href: "/szukaj", label: "Szukaj", icon: "search" },
  { href: "/kreator/pozwolenie-zgloszenie", label: "Kreator", icon: "list-tree" },
  { href: "/sciezki", label: "Krok po kroku", icon: "list-checks" },
  { href: "/slowniczek", label: "Słowniczek", icon: "book-open" },
  { href: "/akty", label: "Akty", icon: "library" },
];

export function NavLinks({ id }: { id?: string }) {
  const pathname = usePathname();
  return (
    <nav className="pb-nav" aria-label="Główna nawigacja" id={id}>
      <ul>
        {LINKS.map((l) => {
          const section = "/" + l.href.split("/")[1];
          const active = pathname === section || pathname.startsWith(section + "/");
          return (
            <li key={l.href}>
              <Link href={l.href} aria-current={active ? "page" : undefined}>
                <Icon name={l.icon} />
                {l.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
