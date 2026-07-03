"use client";

import { ThemeToggle } from "@/components/theme/ThemeToggle";

/**
 * The app chrome for verity.codes — deliberately minimal so the compare workspace is
 * the focus. The deep science/docs live on docs.verity.codes and the raw developer
 * reference on api.verity.codes; both are cross-host, so plain <a> (never next/link).
 */
export function AppNav() {
  return (
    <header className="fixed inset-x-0 top-0 z-30 backdrop-blur-md [mask-image:linear-gradient(to_bottom,black_55%,transparent)] bg-[color-mix(in_srgb,var(--background)_45%,transparent)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <a href="/" className="font-display text-xl font-semibold tracking-tight">
            <span className="accent-text">Verity</span>
          </a>
          {/* Honest-maturity signal: the engine/API is v0.1.0 — link to where things stand. */}
          <a
            href="https://docs.verity.codes/docs#status"
            title="Verity is a research preview — see status & roadmap"
            className="glass hidden whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-medium text-foreground/70 transition hover:text-foreground sm:inline-block"
          >
            Research preview
          </a>
        </div>
        <nav aria-label="Primary" className="flex items-center gap-4 sm:gap-5">
          <a
            href="https://app.verity.codes"
            className="whitespace-nowrap text-sm font-medium text-accent transition hover:opacity-80"
          >
            Studio ↗
          </a>
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
        </nav>
      </div>
    </header>
  );
}
