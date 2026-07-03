import type { Metadata } from "next";
import { HostMap } from "@/components/docs/HostMap";

const DOCS_HOME_TITLE = "Verity documentation — method, validation, data, and API";
const DOCS_HOME_DESC =
  "The method, the open benchmark, the reference data catalog, and the API behind Verity's calibrated forensic surface comparison.";

export const metadata: Metadata = {
  // `absolute` so the layout's "%s · Verity docs" template doesn't double the
  // wordmark on the docs home (would read "Verity documentation … · Verity docs").
  title: { absolute: DOCS_HOME_TITLE },
  description: DOCS_HOME_DESC,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Verity",
    url: "/",
    title: DOCS_HOME_TITLE,
    description: DOCS_HOME_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity documentation" }],
  },
};

interface DocCard {
  href: string;
  title: string;
  blurb: string;
  external?: boolean;
}

const CARDS: DocCard[] = [
  {
    href: "/method",
    title: "The method",
    blurb:
      "How a scan becomes a calibrated likelihood ratio — leveling, signature extraction, alignment, congruent matching regions, and calibration — step by step on real marks.",
  },
  {
    href: "/why",
    title: "Why Verity",
    blurb:
      "What was missing: one calibrated, explainable, open method across mark types, where the statistics decide and the cost is characterized — not a black-box match.",
  },
  {
    href: "/benchmark",
    title: "The open benchmark",
    blurb:
      "Frozen, source-disjoint splits scored on Cllr, calibration loss, and AUC. A leaderboard anyone can submit to, with a downloadable replication kit.",
  },
  {
    href: "/catalog",
    title: "The data catalog",
    blurb:
      "Browse the forensic scans behind the references — striated, impressed, and toolmark — content-addressed and downloadable as raw X3P.",
  },
  {
    href: "/references",
    title: "References",
    blurb:
      "The foundational methods, standards, benchmark datasets, and calibration literature Verity builds on, with relevance notes.",
  },
  {
    href: "/lineage",
    title: "Scientific lineage",
    blurb:
      "The published research Verity operationalizes — automatic bullet-land matching, Congruent Matching Cells, and the open-data ecosystem — plus the downloadable validation report.",
  },
  {
    href: "/docs",
    title: "Use Verity",
    blurb:
      "Quickstart, core concepts (LR, Cllr, CMR), the REST API and reproducibility, the X3P codec, and the system architecture.",
  },
  {
    href: "https://api.verity.codes/scalar",
    title: "API reference",
    blurb:
      "The interactive OpenAPI reference for the comparison API — endpoints, schemas, and live request examples.",
    external: true,
  },
];

export default function DocsLanding() {
  return (
    <main id="main" className="mx-auto w-full max-w-5xl px-6 pb-24 pt-28 sm:pt-36">
      <div className="rise max-w-3xl">
        <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
          <span className="h-1.5 w-1.5 rounded-full bg-brass" />
          The science behind Verity
        </span>
        <h1 className="mt-6 font-display text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl">
          The method, weighed <span className="accent-text">in the open</span>.
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-relaxed text-foreground/80">
          Everything behind the calibrated likelihood ratio — the method, the open benchmark,
          the reference data, and the API. The app itself lives at{" "}
          <a
            href="https://verity.codes"
            className="text-accent underline decoration-border underline-offset-2 transition hover:decoration-accent"
          >
            verity.codes
          </a>
          .
        </p>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-muted">
          Start where you fit: scientists →{" "}
          <a href="/method" className="text-accent underline decoration-border underline-offset-2 transition hover:decoration-accent">
            the method
          </a>{" "}
          · developers →{" "}
          <a href="/docs" className="text-accent underline decoration-border underline-offset-2 transition hover:decoration-accent">
            use Verity
          </a>{" "}
          · examiners →{" "}
          <a href="/why" className="text-accent underline decoration-border underline-offset-2 transition hover:decoration-accent">
            why it exists
          </a>
          .
        </p>
      </div>

      <div className="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {CARDS.map((c) => (
          <a
            key={c.href}
            href={c.href}
            {...(c.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            className="glass group flex flex-col gap-2 rounded-2xl p-6 transition hover:border-accent/40"
          >
            <h2 className="font-display text-xl font-medium text-foreground">
              {c.title}
              <span aria-hidden className="ml-1 text-accent transition group-hover:translate-x-0.5">
                {c.external ? " ↗" : " →"}
              </span>
              {c.external && <span className="sr-only"> (opens in new tab)</span>}
            </h2>
            <p className="text-sm leading-relaxed text-muted">{c.blurb}</p>
          </a>
        ))}
      </div>

      <HostMap />
    </main>
  );
}
