"use client";

import { ThemeToggle } from "@/components/theme/ThemeToggle";

/**
 * The slim chrome for app.verity.codes — full-bleed (no centered marketing column) so the
 * stage owns the screen. The wordmark and cross-host links (Docs / API) use plain <a>.
 */
export function StudioNav() {
  return (
    <header className="flex shrink-0 items-center justify-between border-b border-border px-4 py-2.5 sm:px-6">
      <a href="https://verity.codes" className="font-display text-lg font-semibold tracking-tight">
        <span className="accent-text">Verity</span>
        <span className="ml-1.5 align-middle font-sans text-xs font-normal text-muted">studio</span>
      </a>
      <div className="flex items-center gap-4 sm:gap-5">
        <a
          href="https://docs.verity.codes"
          className="whitespace-nowrap text-sm text-foreground/70 transition hover:text-foreground"
        >
          Docs ↗
        </a>
        <a
          href="https://api.verity.codes/scalar"
          target="_blank"
          rel="noopener noreferrer"
          className="whitespace-nowrap text-sm text-foreground/70 transition hover:text-foreground"
        >
          API ↗
        </a>
        <ThemeToggle />
      </div>
    </header>
  );
}
