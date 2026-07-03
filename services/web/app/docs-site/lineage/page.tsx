import type { Metadata } from "next";
import { Reveal } from "@/components/Reveal";
import { JsonLd, docsArticleJsonLd } from "@/components/seo/JsonLd";

const LINEAGE_TITLE = "Scientific lineage — the research Verity operationalizes";
// Kept ≤160 chars for a clean SERP snippet (was ~318). The full lineage — Hare,
// Hofmann & Carriquiry (2017), Song's CMC, and the non-affiliation disclaimer —
// stays in the page body; this is only the meta summary.
const LINEAGE_DESC =
  "The prior open research Verity operationalizes — automatic bullet-land matching and Congruent Matching Cells. Independent; unaffiliated with CSAFE or NIST.";

export const metadata: Metadata = {
  title: LINEAGE_TITLE,
  description: LINEAGE_DESC,
  alternates: { canonical: "/lineage" },
  openGraph: {
    type: "article",
    siteName: "Verity",
    url: "/lineage",
    title: LINEAGE_TITLE,
    description: LINEAGE_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity — scientific lineage" }],
  },
};

interface Pillar {
  tag: string;
  title: string;
  body: string;
  cites: { label: string; href: string }[];
}

// The research Verity descends from. Framed strictly as intellectual lineage —
// citation here means "we build on this published work", never affiliation,
// endorsement, or collaboration.
const PILLARS: Pillar[] = [
  {
    tag: "The method",
    title: "Automatic bullet-land matching",
    body: "Verity's bullet-land pipeline descends from the published automatic-matching method — crosscut signatures, alignment, and a learned similarity score — the research line that produced the open bulletxtrctr toolchain. Verity re-implements the ideas in an independent pipeline and benchmarks against the original on the same public data.",
    cites: [
      {
        label: "Hare, Hofmann & Carriquiry (2017), AOAS",
        href: "https://doi.org/10.1214/17-AOAS1080",
      },
      {
        label: "bulletxtrctr comparison — Vanderplas et al. (2020)",
        href: "https://doi.org/10.1016/j.forsciint.2020.110167",
      },
    ],
  },
  {
    tag: "The principle",
    title: "Congruent Matching Cells",
    body: "The cell-counting idea at Verity's core is Song's Congruent Matching Cells, developed at NIST for cartridge-case breech faces. Verity generalizes it to Congruent Matching Regions so one pipeline spans striated and impressed marks, rather than a bespoke method per mark type.",
    cites: [
      {
        label: "Song (2015), NIST",
        href: "https://www.nist.gov/publications/proposed-congruent-matching-cells-cmc-method-ballistic-identifications-and-evidence",
      },
      {
        label: "Song et al. (2018)",
        href: "https://doi.org/10.1016/j.forsciint.2017.12.013",
      },
    ],
  },
  {
    tag: "The evidence",
    title: "The open-data ecosystem",
    body: "Verity is validated against the public benchmark data the research community built and shares — the Hamby 10-barrel bullet sets from the open NIST NBTRD, the Fadul consecutively-manufactured cartridge cases from CSAFE-ISU's open cartridgeCaseScans repository, and screwdriver toolmarks from the open tmaRks dataset — and its native X3P codec is interoperable with the community's x3ptools reader.",
    cites: [
      {
        label: "NIST NBTRD",
        href: "https://doi.org/10.6028/jres.125.004",
      },
      {
        label: "x3ptools (CRAN)",
        href: "https://doi.org/10.32614/CRAN.package.x3ptools",
      },
    ],
  },
];

interface Contribution {
  title: string;
  body: string;
}

// What Verity adds on top of that lineage — the production layer, nothing more.
const CONTRIBUTIONS: Contribution[] = [
  {
    title: "An open X3P codec",
    body: "A native Rust reader/writer for X3P (ISO 25178-72) with Python and R bindings — bit-identical I/O across languages.",
  },
  {
    title: "One calibrated pipeline",
    body: "Striated and impressed marks flow through a single method that reports a bounded, calibrated likelihood ratio with region-level attribution — not just a score.",
  },
  {
    title: "Reproducible validation",
    body: "Source-disjoint, per-dataset evaluation — AUC and Cllr reported without pooling across firearm makes — re-runnable as references grow.",
  },
  {
    title: "Auditable reports",
    body: "A per-comparison artifact: the LR, its verbal weight, the regions that drove it, and an explicit statement of scope.",
  },
];

const DOWNLOADS = [
  { href: "/sample-validation-report.pdf", label: "Validation report (Hamby-252)" },
  { href: "/sample-comparison-report.pdf", label: "Sample comparison report" },
  { href: "/whitepaper.pdf", label: "Technical white paper" },
];

export default function LineagePage() {
  return (
    <>
      <JsonLd data={docsArticleJsonLd({ slug: "lineage", title: LINEAGE_TITLE, description: LINEAGE_DESC, breadcrumb: "Scientific lineage" })} />

      <main id="main" className="mx-auto w-full max-w-4xl px-6 pb-24 pt-28 sm:pt-36">
        <section className="rise max-w-3xl">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Where the science comes from
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
            Scientific <span className="accent-text">lineage</span>
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-foreground/80">
            Verity did not invent the science of forensic surface comparison — it operationalizes
            published, open research. The methods below are the shoulders it stands on;
            Verity&rsquo;s contribution is the production layer built on top of them. Citation here
            denotes intellectual lineage only, never affiliation or endorsement.
          </p>
        </section>

        <Reveal className="mt-12">
          <div className="grid items-start gap-5 lg:grid-cols-3">
            {PILLARS.map((p) => (
              <div key={p.title} className="glass flex flex-col rounded-2xl p-6">
                <span className="text-[11px] font-medium uppercase tracking-wider text-accent">
                  {p.tag}
                </span>
                <h2 className="mt-1.5 font-display text-xl font-medium text-foreground">
                  {p.title}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-foreground/75">{p.body}</p>
                <div className="mt-auto flex flex-col gap-1.5 pt-4">
                  {p.cites.map((c) => (
                    <a
                      key={c.href}
                      href={c.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-muted underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
                    >
                      {c.label} ↗
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal className="mt-12">
          <div className="glass rounded-2xl p-6 sm:p-7 ring-1 ring-accent/30">
            <span className="text-[11px] font-medium uppercase tracking-wider text-accent">
              Independence
            </span>
            <h2 className="mt-1.5 font-display text-xl font-medium text-foreground sm:text-2xl">
              Not affiliated, and not claiming to be
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-foreground/80">
              Verity is an independent project. It is not affiliated with, endorsed by, or developed
              in partnership with CSAFE, NIST, or Iowa State University. The research cited on this
              page is public, peer-reviewed work that anyone may build on — building on it implies
              nothing about its authors&rsquo; or their institutions&rsquo; views of Verity.
            </p>
          </div>
        </Reveal>

        <Reveal className="mt-16">
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            What Verity adds
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/80">
            The lineage above is the science. Verity&rsquo;s own contribution is deliberately narrow:
            the deployment, calibration, and audit layer that carries that science into practice.
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {CONTRIBUTIONS.map((c) => (
              <div key={c.title} className="glass rounded-2xl p-6">
                <h3 className="font-display text-lg font-medium text-foreground">{c.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-foreground/75">{c.body}</p>
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal className="mt-12">
          <div className="glass rounded-2xl p-6 sm:p-7">
            <span className="text-[11px] font-medium uppercase tracking-wider text-accent">
              See it for yourself
            </span>
            <h2 className="mt-1.5 font-display text-xl font-medium text-foreground sm:text-2xl">
              Real, downloadable artifacts
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/75">
              Each is generated by the live system from public benchmark data — the validation
              harness, the per-comparison report, and the technical write-up.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              {DOWNLOADS.map((d) => (
                <a
                  key={d.href}
                  href={d.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full border border-border bg-foreground/[0.03] px-4 py-2 text-sm font-medium text-foreground/80 transition hover:border-accent/40 hover:text-accent"
                >
                  {d.label} &darr;
                </a>
              ))}
            </div>
          </div>
        </Reveal>

        <Reveal className="mt-16">
          <div className="overflow-hidden rounded-[1.45rem] bg-gradient-to-br from-brass via-primary to-brass p-[1.5px] shadow-xl shadow-[#0e2a47]/15">
            <div className="rounded-[1.35rem] bg-background p-8 text-center">
              <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
                Built on the field, not against it
              </h2>
              <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-foreground/80">
                Verity does not replace the science or the examiner — it deploys, calibrates, and
                makes auditable what the research community has published. The full bibliography
                traces every claim on this site back to the scholarly record.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <a
                  href="/why"
                  className="glass rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
                >
                  Why Verity exists
                </a>
                <a
                  href="/references"
                  className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-[#f4f1ea] shadow-lg shadow-[#0e2a47]/20 transition hover:opacity-90"
                >
                  The full bibliography →
                </a>
              </div>
            </div>
          </div>
        </Reveal>
      </main>
    </>
  );
}
