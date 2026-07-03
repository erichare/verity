import { LinkArrow } from "@/components/LinkArrow";

interface HostRow {
  href: string;
  host: string;
  blurb: string;
  external?: boolean;
  here?: boolean;
}

// The five-host split, explained once, compactly. Lives on the docs landing page
// (its own component so the landing page edit stays a one-line insert).
const HOSTS: HostRow[] = [
  {
    href: "https://verity.codes",
    host: "verity.codes",
    blurb: "The compare workspace — pick or upload two marks, get the calibrated likelihood ratio.",
  },
  {
    href: "https://app.verity.codes",
    host: "app.verity.codes",
    blurb: "Verity Studio — a full-screen, glass-box view of every pipeline stage on a real comparison.",
  },
  {
    href: "https://docs.verity.codes",
    host: "docs.verity.codes",
    blurb: "This site — the method, validation, benchmark, data catalog, references, and guides.",
    here: true,
  },
  {
    href: "https://api.verity.codes/scalar",
    host: "api.verity.codes",
    blurb: "The comparison API — upload X3P scans, get a ComparisonReport. Interactive OpenAPI reference.",
    external: true,
  },
  {
    href: "https://data.verity.codes/scalar",
    host: "data.verity.codes",
    blurb: "The data API — the scan catalog, frozen benchmark splits, leaderboard, and replication kits.",
    external: true,
  },
];

/** A compact map of Verity's five hosts — what each subdomain is for. */
export function HostMap() {
  return (
    <section aria-labelledby="host-map-heading" className="mt-16">
      <h2
        id="host-map-heading"
        className="font-display text-2xl font-medium text-foreground"
      >
        One project, <span className="accent-text">five hosts</span>
      </h2>
      <p className="mt-2 max-w-2xl text-sm text-muted">
        Verity is one open codebase deployed across five subdomains — each does exactly one
        job.
      </p>
      <ul className="glass mt-6 divide-y divide-border/60 rounded-2xl">
        {HOSTS.map((h) => (
          <li key={h.host} className="flex flex-col gap-1 px-5 py-3.5 sm:flex-row sm:items-baseline sm:gap-4">
            <span className="shrink-0 sm:w-44">
              <a
                href={h.href}
                {...(h.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                className="font-mono text-sm text-foreground/80 transition hover:text-accent"
              >
                {h.host}
                <LinkArrow
                  kind={h.external ? "external" : "right"}
                  className="ml-1 text-accent"
                />
                {h.external && <span className="sr-only"> (opens in new tab)</span>}
              </a>
              {h.here && (
                <span className="ml-2 rounded-full border border-border px-2 py-0.5 text-[10px] text-muted sm:ml-0 sm:mt-1 sm:block sm:w-fit">
                  you are here
                </span>
              )}
            </span>
            <span className="text-sm leading-relaxed text-muted">{h.blurb}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
