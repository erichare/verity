const GITHUB = "https://github.com/erichare/verity";

// The five-host map — one line each. This is the single place the whole split is
// spelled out, and the footer renders on all three web shells, so every host can
// reach every other one (including data.verity.codes, which is otherwise invisible).
const HOSTS: { href: string; host: string; role: string; external?: boolean }[] = [
  { href: "https://verity.codes", host: "verity.codes", role: "compare workspace" },
  { href: "https://app.verity.codes", host: "app.verity.codes", role: "Studio — the pipeline, stage by stage" },
  { href: "https://docs.verity.codes", host: "docs.verity.codes", role: "documentation & the science" },
  { href: "https://api.verity.codes/scalar", host: "api.verity.codes", role: "comparison API", external: true },
  { href: "https://data.verity.codes/scalar", host: "data.verity.codes", role: "catalog & benchmark data API", external: true },
];

const PROJECT: { href: string; label: string; external?: boolean }[] = [
  { href: GITHUB, label: "GitHub", external: true },
  // The PDF resolves from /public identically on every host (proxy.ts skips *.pdf).
  { href: "/whitepaper.pdf", label: "White paper (PDF)", external: true },
  { href: "https://docs.verity.codes/about", label: "About & contact" },
  { href: `${GITHUB}/issues`, label: "Report an issue", external: true },
];

function FooterLink({
  href,
  external,
  children,
  className = "",
}: {
  href: string;
  external?: boolean;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <a
      href={href}
      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className={`transition hover:text-accent ${className}`}
    >
      {children}
    </a>
  );
}

/**
 * The shared trust chrome, rendered on all three web shells: the homepage
 * (verity.codes), the docs layout (docs.verity.codes), and — as the compact
 * variant — the viewport-locked Studio (app.verity.codes). Quiet and archival:
 * hairline top border, muted ink, no panels. All links are plain <a> (cross-host).
 *
 * The scope disclaimer is the same legally-relevant text the homepage footer has
 * always carried — do not shorten or remove it.
 */
export function SiteFooter({
  variant = "full",
  className = "",
}: {
  variant?: "full" | "compact";
  className?: string;
}) {
  if (variant === "compact") {
    // One slim row for the Studio's viewport-locked shell.
    return (
      <footer
        className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-border px-4 py-2 sm:px-6 ${className}`}
      >
        <p className="hidden text-[11px] text-muted sm:block">
          A calibrated weight of evidence — never a verdict.
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted">
          <FooterLink href={GITHUB} external>
            GitHub ↗
          </FooterLink>
          <span className="whitespace-nowrap">
            <FooterLink href={`${GITHUB}/blob/main/LICENSE-MIT`} external>
              MIT
            </FooterLink>
            {" / "}
            <FooterLink href={`${GITHUB}/blob/main/LICENSE-APACHE`} external>
              Apache-2.0
            </FooterLink>
          </span>
          <FooterLink href="/whitepaper.pdf" external>
            White paper
          </FooterLink>
          <FooterLink href="https://data.verity.codes/scalar" external>
            Data API ↗
          </FooterLink>
          <FooterLink href="https://docs.verity.codes/about">About ↗</FooterLink>
        </div>
      </footer>
    );
  }

  return (
    <footer className={`border-t border-border/60 ${className}`}>
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-6 py-10 md:flex-row md:justify-between">
        <div className="max-w-sm">
          <p className="font-display text-lg font-semibold tracking-tight">
            <span className="accent-text">Verity</span>
          </p>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            The representation reports a calibrated likelihood ratio; it never makes the
            decision. Not a claim about the error rate of forensic examination, which remains
            unknown.
          </p>
          <p className="mt-3 text-xs leading-relaxed text-muted">
            Open source, dual-licensed{" "}
            <FooterLink
              href={`${GITHUB}/blob/main/LICENSE-MIT`}
              external
              className="underline decoration-border underline-offset-2 hover:decoration-accent"
            >
              MIT
            </FooterLink>{" "}
            or{" "}
            <FooterLink
              href={`${GITHUB}/blob/main/LICENSE-APACHE`}
              external
              className="underline decoration-border underline-offset-2 hover:decoration-accent"
            >
              Apache-2.0
            </FooterLink>
            , at your option.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 sm:gap-14">
          <nav aria-label="Project">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted">
              Project
            </p>
            <ul className="mt-3 space-y-2 text-xs text-foreground/70">
              {PROJECT.map((l) => (
                <li key={l.label}>
                  <FooterLink href={l.href} external={l.external}>
                    {l.label}
                    {l.external ? " ↗" : ""}
                  </FooterLink>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label="Verity hosts">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted">
              One project, five hosts
            </p>
            <ul className="mt-3 space-y-2 text-xs">
              {HOSTS.map((h) => (
                <li key={h.host} className="text-muted">
                  <FooterLink
                    href={h.href}
                    external={h.external}
                    className="font-mono text-foreground/70"
                  >
                    {h.host}
                  </FooterLink>
                  <span aria-hidden> — </span>
                  {h.role}
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </div>
    </footer>
  );
}
