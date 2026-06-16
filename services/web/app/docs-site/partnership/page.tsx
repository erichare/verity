import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Reveal } from "@/components/Reveal";

export const metadata: Metadata = {
  title: "CSAFE × Verity — a proposed partnership",
  description:
    "A proposal: pair CSAFE's foundational forensic-statistics research with Verity's production deployment, calibration, and tooling. What each side would bring, and a modest set of first milestones.",
};

interface Item {
  title: string;
  body: string;
}

const VERITY_BRINGS: Item[] = [
  {
    title: "An open X3P codec",
    body: "A native Rust reader/writer for X3P (ISO 25178-72) with Python and R bindings — bit-identical I/O across languages, interoperable with x3ptools.",
  },
  {
    title: "A deployed calibrated-LR API",
    body: "A hosted comparison service that turns a pair of scans into a bounded, calibrated likelihood ratio with region-level attribution — not just a score.",
  },
  {
    title: "A data catalog",
    body: "A normalized, content-addressed store and manifest-driven ingestion for forensic scans (NBTRD, Figshare), with KM/KNM labels derived from the study hierarchy.",
  },
  {
    title: "Calibration as a service",
    body: "Calibrating any score onto a named reference population, with a characterized cost (Cllr) and an empirical cap (ELUB-inspired) on what the data can support.",
  },
  {
    title: "Automated validation reports",
    body: "Reproducible, source-disjoint, per-dataset evaluation — AUC and Cllr reported without pooling across firearm makes — re-runnable as references grow.",
  },
  {
    title: "Court-ready per-comparison reports",
    body: "An auditable artifact per comparison: the LR, its verbal weight, the regions that drove it, and an explicit statement of scope.",
  },
];

const CSAFE_BRINGS: Item[] = [
  {
    title: "Foundational methods",
    body: "The automatic bullet-matching work (Hare, Hofmann & Carriquiry, 2017) and the broader CMC/CMR research line that Verity operationalizes.",
  },
  {
    title: "Benchmark datasets",
    body: "The public, well-characterized data the field relies on — Hamby bullet sets, consecutively-manufactured cartridge and toolmark studies.",
  },
  {
    title: "Validation expertise",
    body: "Decades of rigor on study design, error-rate estimation, and the methodological pitfalls of black-box validation.",
  },
  {
    title: "Scientific credibility",
    body: "Independent, academic grounding — the standard against which a deployed system should be measured and reviewed.",
  },
];

interface Milestone {
  n: string;
  title: string;
  body: string;
}

const MILESTONES: Milestone[] = [
  {
    n: "01",
    title: "Reproduce a published result, end to end",
    body: "Re-run an existing CSAFE bullet-matching result through Verity's open codec and calibration layer, and publish the reproduction as a versioned validation report.",
  },
  {
    n: "02",
    title: "Calibrate on a named reference together",
    body: "Jointly select a reference population, fit and publish its calibration (Cllr, empirical LR cap), and document exactly what claims that reference can and cannot support.",
  },
  {
    n: "03",
    title: "Open the validation harness",
    body: "Release the source-disjoint, per-dataset evaluation harness so any new method or dataset can be scored the same honest way, by anyone.",
  },
  {
    n: "04",
    title: "Draft a court-ready report template",
    body: "Co-design a per-comparison report — LR, attribution, scope — that meets the bar CSAFE's reviews call for, and circulate it for community feedback.",
  },
];

function BringsCard({
  eyebrow,
  title,
  items,
  accent,
}: {
  eyebrow: string;
  title: ReactNode;
  items: Item[];
  accent: boolean;
}) {
  return (
    <div
      className={`glass flex flex-col rounded-2xl p-6 sm:p-7 ${
        accent ? "ring-1 ring-accent/30" : ""
      }`}
    >
      <span className="text-[11px] font-medium uppercase tracking-wider text-accent">{eyebrow}</span>
      <h2 className="mt-1.5 font-display text-xl font-medium text-foreground sm:text-2xl">{title}</h2>
      <ul className="mt-5 space-y-4">
        {items.map((it) => (
          <li key={it.title} className="flex gap-3">
            <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
            <div>
              <p className="text-sm font-medium text-foreground">{it.title}</p>
              <p className="mt-0.5 text-sm leading-relaxed text-foreground/75">{it.body}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function PartnershipPage() {
  return (
    <>

      <main className="mx-auto w-full max-w-5xl px-6 pb-24 pt-28 sm:pt-36">
        <section className="rise max-w-3xl">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            A proposal — not a current affiliation
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
            <span className="accent-text">CSAFE × Verity</span>
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-foreground/80">
            Verity is the production, deployment, and calibration layer for a science it did not
            invent. The natural next step would be to bring the two together: CSAFE&rsquo;s foundational
            research and the deployed, calibrated, auditable tooling that could carry it into practice.
            What follows is a proposal for what such a collaboration <em>could</em> look like — written
            in the future tense, on purpose.
          </p>
        </section>

        <Reveal className="mt-12">
          <div className="grid items-start gap-5 lg:grid-cols-2">
            <BringsCard
              eyebrow="What Verity would bring"
              title={
                <>
                  The <span className="accent-text">production layer</span>
                </>
              }
              items={VERITY_BRINGS}
              accent
            />
            <BringsCard
              eyebrow="What CSAFE brings"
              title={
                <>
                  The <span className="accent-text">science</span>
                </>
              }
              items={CSAFE_BRINGS}
              accent={false}
            />
          </div>
        </Reveal>

        <Reveal className="mt-12">
          <div className="glass rounded-2xl p-6 sm:p-7">
            <span className="text-[11px] font-medium uppercase tracking-wider text-accent">
              The actual artifacts
            </span>
            <h2 className="mt-1.5 font-display text-xl font-medium text-foreground sm:text-2xl">
              Not slides &mdash; <span className="accent-text">real, downloadable deliverables</span>
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/75">
              Each is generated by the live system from public benchmark data &mdash; the same
              machinery a CSAFE engagement would run on a properly powered reference.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              {[
                { href: "/sample-validation-report.pdf", label: "Validation report (Hamby-252)" },
                { href: "/sample-comparison-report.pdf", label: "Court-ready comparison report" },
                { href: "/whitepaper.pdf", label: "Technical white paper" },
              ].map((d) => (
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
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            A proposed engagement
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/80">
            Modest, concrete, and sequenced so each step produces something publishable on its own. No
            step assumes the next; any one of them would stand alone as a useful contribution.
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {MILESTONES.map((m) => (
              <div key={m.n} className="glass rounded-2xl p-6">
                <div className="font-display text-sm font-semibold text-accent">{m.n}</div>
                <h3 className="mt-1 font-display text-lg font-medium text-foreground">{m.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-foreground/75">{m.body}</p>
              </div>
            ))}
          </div>
        </Reveal>

        <Reveal className="mt-16">
          <div className="overflow-hidden rounded-[1.45rem] bg-gradient-to-br from-brass via-primary to-brass p-[1.5px] shadow-xl shadow-[#0e2a47]/15">
            <div className="rounded-[1.35rem] bg-background p-8 text-center">
              <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
                The honest version of the offer
              </h2>
              <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-foreground/80">
                Verity does not replace the science or the examiner — it deploys, calibrates, and makes
                auditable what the research community has built. If that is useful, the door is open to
                build it together.
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
                  The science behind it →
                </a>
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal className="mt-12">
          <p className="mx-auto max-w-3xl text-center text-xs leading-relaxed text-muted">
            <strong className="font-medium text-foreground/70">Non-affiliation.</strong> This page
            describes a proposed collaboration only. Verity is an independent project and is not
            affiliated with, sponsored by, or endorsed by CSAFE or Iowa State University. No partnership
            currently exists, and nothing here should be read as implying one.
          </p>
        </Reveal>
      </main>
    </>
  );
}
