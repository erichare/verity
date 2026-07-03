"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

interface DocsLink {
  href: string;
  label: string;
  external?: boolean;
}

// The science/docs nav for docs.verity.codes. Order matters — left to right.
const DOCS_LINKS: DocsLink[] = [
  { href: "/method", label: "Method" },
  { href: "/why", label: "Why" },
  { href: "/benchmark", label: "Benchmark" },
  { href: "/catalog", label: "Catalog" },
  { href: "/references", label: "References" },
  { href: "/lineage", label: "Lineage" },
  { href: "/docs", label: "Use Verity" },
  { href: "https://api.verity.codes/scalar", label: "API", external: true },
  { href: "/whitepaper.pdf", label: "White paper", external: true },
];

/**
 * The content nav for the docs subdomain, rendered once in the docs-site layout. On
 * docs.verity.codes a request to /method is rewritten internally to /docs-site/method
 * (see proxy.ts); usePathname reflects the public path, but we strip the prefix
 * defensively so the active-tab underline is correct either way. The wordmark and the
 * "Open the app" CTA point back to the app host (cross-host → plain <a>).
 *
 * The full horizontal nav only fits from lg up; below that it collapses into a menu
 * button + dropdown panel so nothing is cut off on phones or tablets.
 */
export function DocsSiteNav() {
  const path = usePathname().replace(/^\/docs-site/, "") || "/";
  const [open, setOpen] = useState(false);

  // Close the mobile menu on route change (the path updates after navigation).
  useEffect(() => {
    setOpen(false);
  }, [path]);

  function renderLink(link: DocsLink, block: boolean) {
    const active = !link.external && path === link.href;
    return (
      <a
        key={link.label}
        href={link.href}
        {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
        aria-current={active ? "page" : undefined}
        onClick={() => setOpen(false)}
        className={
          block
            ? `border-b border-border/40 py-2.5 text-sm transition ${
                active ? "font-medium text-foreground" : "text-foreground/70 hover:text-foreground"
              }`
            : `relative whitespace-nowrap pb-1.5 text-sm transition ${
                active ? "font-medium text-foreground" : "text-foreground/70 hover:text-foreground"
              }`
        }
      >
        {link.label}
        {!block && active && (
          <span
            aria-hidden
            className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-accent"
          />
        )}
      </a>
    );
  }

  return (
    <header className="fixed inset-x-0 top-0 z-30 backdrop-blur-md bg-[color-mix(in_srgb,var(--background)_55%,transparent)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <a href="https://verity.codes" className="font-display text-xl font-semibold tracking-tight">
          <span className="accent-text">Verity</span>
          <span className="ml-1.5 align-middle text-xs font-normal text-muted">docs</span>
        </a>

        {/* lg+: the full horizontal nav (every item fits without scrolling). */}
        <nav
          aria-label="Documentation"
          className="hidden items-center gap-4 lg:flex xl:gap-5"
        >
          {DOCS_LINKS.map((link) => renderLink(link, false))}
          <a
            href="https://app.verity.codes"
            className="whitespace-nowrap text-sm font-medium text-accent transition hover:opacity-80"
          >
            Studio ↗
          </a>
          <ThemeToggle />
        </nav>

        {/* Below lg: theme toggle stays reachable; the rest collapses behind a menu. */}
        <div className="flex items-center gap-2 lg:hidden">
          <ThemeToggle />
          <button
            type="button"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
            className="glass inline-flex h-9 w-9 items-center justify-center rounded-full text-foreground/70 transition hover:text-foreground"
          >
            {open ? <CloseIcon /> : <MenuIcon />}
          </button>
        </div>
      </div>

      {/* Mobile/tablet dropdown panel. */}
      {open && (
        <nav
          aria-label="Documentation (mobile)"
          className="border-t border-border/60 px-4 pb-4 pt-1 sm:px-6 lg:hidden"
        >
          <div className="mx-auto flex max-w-6xl flex-col">
            {DOCS_LINKS.map((link) => renderLink(link, true))}
            <a
              href="https://app.verity.codes"
              className="border-b border-border/40 py-2.5 text-sm font-medium text-accent"
            >
              Studio ↗
            </a>
            <a
              href="https://verity.codes"
              className="py-2.5 text-sm font-medium text-accent"
            >
              Open the app ↗
            </a>
          </div>
        </nav>
      )}
    </header>
  );
}

function MenuIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M3 6h18M3 12h18M3 18h18" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}
