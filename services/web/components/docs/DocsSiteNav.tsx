"use client";

import { usePathname } from "next/navigation";
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
 */
export function DocsSiteNav() {
  const path = usePathname().replace(/^\/docs-site/, "") || "/";
  return (
    <header className="fixed inset-x-0 top-0 z-30 backdrop-blur-md bg-[color-mix(in_srgb,var(--background)_55%,transparent)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <a href="https://verity.codes" className="font-display text-xl font-semibold tracking-tight">
          <span className="accent-text">Verity</span>
          <span className="ml-1.5 align-middle text-xs font-normal text-muted">docs</span>
        </a>
        <div className="flex items-center gap-4 overflow-x-auto sm:gap-5">
          {DOCS_LINKS.map((link) => {
            const active = !link.external && path === link.href;
            return (
              <a
                key={link.label}
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
          })}
          <a
            href="https://verity.codes"
            className="whitespace-nowrap text-sm font-medium text-accent transition hover:opacity-80"
          >
            Open the app ↗
          </a>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
