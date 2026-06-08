"use client";

import { usePathname } from "next/navigation";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

/**
 * The shared, fixed top navigation for every page. It highlights the tab for the
 * current route (via {@link usePathname}). The homepage passes `cinematic` for the
 * scrim/mask treatment that fades the bar into the hero; content pages use the
 * default solid-blur bar. One coherent definition of the nav lives here.
 */

export interface NavLink {
  href: string;
  label: string;
  external?: boolean;
}

// The canonical site navigation. Order matters — left to right.
export const NAV_LINKS: NavLink[] = [
  { href: "/method", label: "Method" },
  { href: "/why", label: "Why" },
  { href: "/catalog", label: "Catalog" },
  { href: "/docs", label: "Docs" },
  // The /partnership page exists but is intentionally unlinked here (kept private
  // — shared deliberately, not surfaced in the public nav).
  { href: "/references", label: "References" },
  { href: "/whitepaper.pdf", label: "White paper", external: true },
  { href: "https://api.verity.codes/scalar", label: "API", external: true },
];

function NavAnchor({ link, active }: { link: NavLink; active: boolean }) {
  return (
    <a
      href={link.href}
      {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      aria-current={active ? "page" : undefined}
      className={`relative whitespace-nowrap pb-1.5 text-sm transition ${
        active ? "font-medium text-foreground" : "text-foreground/70 hover:text-foreground"
      }`}
    >
      {link.label}
      {active && (
        <span
          aria-hidden
          className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-accent"
        />
      )}
    </a>
  );
}

export function SiteNav({ cinematic = false }: { cinematic?: boolean }) {
  const pathname = usePathname();
  return (
    <header
      className={`fixed inset-x-0 top-0 z-30 backdrop-blur-md ${
        cinematic
          ? "[mask-image:linear-gradient(to_bottom,black_55%,transparent)] bg-[color-mix(in_srgb,var(--background)_45%,transparent)]"
          : "bg-[color-mix(in_srgb,var(--background)_55%,transparent)]"
      }`}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <a href="/" className="font-display text-xl font-semibold tracking-tight">
          <span className="accent-text">Verity</span>
        </a>
        <div className="flex items-center gap-4 overflow-x-auto sm:gap-5">
          {NAV_LINKS.map((link) => (
            <NavAnchor
              key={link.label}
              link={link}
              active={!link.external && pathname === link.href}
            />
          ))}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
