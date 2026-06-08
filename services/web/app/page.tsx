"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { compareMarks, detectDomain, getDomains, type Detection } from "@/lib/api";
import type { ComparisonReport } from "@/lib/types";
import { buildSampleReport } from "@/lib/sample-report";
import ReportView from "@/components/ReportView";
import { Reveal } from "@/components/Reveal";
import { StatBand } from "@/components/home/StatBand";
import { LiveProof } from "@/components/home/LiveProof";
import { MarkBreadth } from "@/components/home/MarkBreadth";
import { WhyTeaser } from "@/components/home/WhyTeaser";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

const HeroSurface = dynamic(() => import("@/components/three/HeroSurface"), {
  ssr: false,
});

const DOMAIN_LABELS: Record<string, string> = {
  impressed: "Impressed — cartridge breech face",
  striated: "Striated — bullet land / toolmark",
};

interface Result {
  data: ComparisonReport;
  sample: boolean;
}

function FilePick({
  label,
  files,
  onPick,
  multiple,
}: {
  label: string;
  files: File[];
  onPick: (f: File[]) => void;
  multiple?: boolean;
}) {
  const summary =
    files.length === 0
      ? multiple
        ? "Choose .x3p land scans…"
        : "Choose an .x3p scan…"
      : files.length === 1
        ? files[0].name
        : `${files.length} scans selected`;
  return (
    <label className="group flex cursor-pointer flex-col gap-1.5 rounded-xl border border-dashed border-border bg-foreground/[0.02] p-4 text-sm transition hover:border-accent/60 hover:bg-foreground/[0.05]">
      <span className="font-medium text-foreground">{label}</span>
      <span className="truncate text-muted group-hover:text-foreground/80">{summary}</span>
      <input
        type="file"
        accept=".x3p"
        multiple={multiple}
        className="hidden"
        onChange={(e) => onPick(Array.from(e.target.files ?? []))}
      />
    </label>
  );
}

function Citations() {
  const refs: [string, string, string][] = [
    ["National Research Council (2009)", "Strengthening Forensic Science in the United States: A Path Forward.", "https://doi.org/10.17226/12589"],
    ["PCAST (2016)", "Forensic Science in Criminal Courts: Ensuring Scientific Validity of Feature-Comparison Methods.", "https://obamawhitehouse.archives.gov/sites/default/files/microsites/ostp/PCAST/pcast_forensic_science_report_final.pdf"],
    ["Cuellar, Vanderplas, Luby & Rosenblum (2024)", "Methodological problems in every black-box study of forensic firearm comparisons.", "https://doi.org/10.1093/lpr/mgae015"],
    ["Song (2013)", "Proposed congruent matching cells (CMC) method for ballistic identification.", "https://www.nist.gov/publications/proposed-congruent-matching-cells-cmc-method-ballistic-identifications-and-evidence"],
    ["Hare, Hofmann & Carriquiry (2017)", "Automatic matching of bullet land impressions. Annals of Applied Statistics.", "https://doi.org/10.1214/17-AOAS1080"],
    ["Brümmer & du Preez (2006)", "Application-independent evaluation of speaker detection — the Cllr cost.", "https://doi.org/10.1016/j.csl.2005.08.001"],
  ];
  return (
    <ul className="mt-4 space-y-1.5 text-xs text-muted">
      {refs.map(([who, what, href]) => (
        <li key={who} className="leading-relaxed">
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline transition hover:text-foreground/80"
          >
            <span className="text-foreground/80 underline decoration-border underline-offset-2 transition group-hover:decoration-accent group-hover:text-accent">
              {who}
            </span>{" "}
            — <span className="italic">{what}</span>
            <span aria-hidden className="ml-0.5 not-italic text-muted/60 transition group-hover:text-accent">↗</span>
          </a>
        </li>
      ))}
    </ul>
  );
}

export default function Home() {
  const [domains, setDomains] = useState<string[]>([]);
  const [domain, setDomain] = useState("striated");
  const [markA, setMarkA] = useState<File[]>([]);
  const [markB, setMarkB] = useState<File[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detected, setDetected] = useState<Detection | null>(null);
  const [manualDomain, setManualDomain] = useState(false);

  useEffect(() => {
    getDomains().then((d) => {
      if (d.length) {
        setDomains(d);
        setDomain((cur) => (d.includes(cur) ? cur : d[0]));
      }
    });
  }, []);

  async function onCompare() {
    if (!markA.length || !markB.length) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult({ data: await compareMarks(domain, markA, markB), sample: false });
    } catch (e) {
      setError(e instanceof Error ? e.message : "comparison failed");
    } finally {
      setLoading(false);
    }
  }

  function onLoadSample() {
    setError(null);
    setResult({ data: buildSampleReport(), sample: true });
  }

  // Auto-detect the mark type from the first scan of Mark A and pre-select it
  // (unless the user has manually chosen a type). Keeps the picked files.
  async function onPickA(files: File[]) {
    setMarkA(files);
    if (!files.length) return;
    const d = await detectDomain(files[0]);
    if (!d) return;
    setDetected(d);
    if (!manualDomain && d.domain !== domain) setDomain(d.domain);
  }

  const shownDomains = domains.length ? domains : ["striated", "impressed"];

  return (
    <>
      {/* Top bar */}
      <header className="fixed inset-x-0 top-0 z-30">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <a href="#top" className="font-display text-xl font-semibold tracking-tight">
            <span className="accent-text">Verity</span>
          </a>
          <div className="flex items-center gap-5">
            <a href="/method" className="text-sm text-foreground/70 transition hover:text-foreground">
              Method
            </a>
            <a href="/why" className="text-sm text-foreground/70 transition hover:text-foreground">
              Why
            </a>
            <a
              href="https://api.verity.codes/scalar"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-foreground/70 transition hover:text-foreground"
            >
              API
            </a>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Cinematic hero */}
      <section
        id="top"
        className="relative isolate flex min-h-[92svh] items-center justify-center overflow-hidden px-6"
      >
        <div className="absolute inset-0 -z-20">
          <HeroSurface />
        </div>
        {/* legibility scrim + fade into the content below */}
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          style={{
            background:
              "radial-gradient(58% 50% at 50% 42%, color-mix(in srgb, var(--background) 62%, transparent), transparent 76%), linear-gradient(to bottom, color-mix(in srgb, var(--background) 40%, transparent) 0%, transparent 22%, transparent 60%, var(--background) 100%)",
          }}
        />

        <div className="rise mx-auto max-w-3xl text-center">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Open-science forensic surface comparison
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-7xl">
            Forensic marks, <span className="accent-text">weighed as evidence</span>.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-foreground/80 sm:text-xl">
            One calibrated, explainable method for comparing forensic surface marks — a{" "}
            <strong className="text-foreground">likelihood ratio with a characterized cost</strong>, and a
            map of <strong className="text-foreground">exactly which regions drove the match</strong>.
          </p>

          <StatBand className="mt-9" />

          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <a
              href="#proof"
              className="rounded-full bg-gradient-to-r from-indigo-500 via-sky-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:opacity-90"
            >
              See it work ↓
            </a>
            <a
              href="/method"
              className="glass rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
            >
              How it works
            </a>
          </div>
          <p className="mt-4 text-xs text-foreground/60">
            <a href="#compare" className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent">
              or upload your own scans →
            </a>
          </p>
        </div>
      </section>

      {/* Content */}
      <main className="mx-auto -mt-10 w-full max-w-4xl px-6 pb-24 sm:-mt-16">
        {/* Live proof — the same method, opposite verdicts */}
        <Reveal>
          <LiveProof />
        </Reveal>

        {/* Breadth — one pipeline, three mark types */}
        <Reveal className="mt-20 sm:mt-28">
          <MarkBreadth />
        </Reveal>

        {/* Why it was necessary */}
        <Reveal className="mt-20 sm:mt-28">
          <WhyTeaser />
        </Reveal>

        {/* Scientific contribution */}
        <Reveal className="mt-16">
          <section id="science" className="glass scroll-mt-20 rounded-2xl p-6 sm:p-8">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
              The scientific contribution
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-foreground/80">
              Two decades of review — the National Research Council&rsquo;s 2009 report and the 2016 PCAST
              report — found that most pattern-evidence disciplines lack demonstrated foundational validity,
              and Cuellar et&nbsp;al. (2024) showed that <em>no</em> discipline has a characterized error
              rate. Existing tools are bespoke to one mark type and stop at an uncalibrated score. Verity
              answers this directly: <strong className="text-foreground">a single, transparent method</strong>{" "}
              that reports a{" "}
              <strong className="text-foreground">calibrated likelihood ratio with a quantified cost (Cllr)</strong>{" "}
              and <strong className="text-foreground">region-level attribution</strong>, spanning striated
              marks (bullets, toolmarks) and impressed marks (cartridge breech faces) by generalizing the
              Congruent Matching Cells method (Song, 2013) to arbitrary toolmarks. The representation only
              produces a score; the reportable decision is a monotone, bounded likelihood ratio — auditable
              no matter how the score was computed.
            </p>
            <details className="group mt-5">
              <summary className="cursor-pointer list-none text-xs font-medium uppercase tracking-wider text-muted transition hover:text-foreground/80">
                <span className="inline-block transition group-open:rotate-90">▸</span> References (6)
              </summary>
              <Citations />
            </details>
          </section>
        </Reveal>

        {/* Comparison tool */}
        <Reveal className="mt-8">
          <section id="compare" className="glass scroll-mt-20 space-y-5 rounded-2xl p-6 sm:p-8">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <h2 className="font-display text-xl font-medium text-foreground">Compare two marks</h2>
              <button
                onClick={onLoadSample}
                className="rounded-full border border-border px-4 py-1.5 text-xs font-medium text-foreground/80 transition hover:border-accent/60 hover:text-foreground"
              >
                No scans handy? Load a sample →
              </button>
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-foreground/80">Mark type</label>
              <select
                value={domain}
                onChange={(e) => {
                  setDomain(e.target.value);
                  setManualDomain(true);
                  setDetected(null);
                  setMarkA([]);
                  setMarkB([]);
                  setResult(null);
                }}
                className="w-full rounded-lg border border-border bg-background/60 px-3 py-2 text-sm text-foreground outline-none focus:border-accent/60"
              >
                {shownDomains.map((d) => (
                  <option key={d} value={d}>
                    {DOMAIN_LABELS[d] ?? d}
                  </option>
                ))}
              </select>
            </div>
            {detected && (
              <p className="text-xs text-muted">
                Auto-detected from your scan:{" "}
                <span className="text-foreground/80">{DOMAIN_LABELS[detected.domain] ?? detected.domain}</span>
                {" "}— change it above if it&rsquo;s wrong.
              </p>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FilePick label="Mark A" files={markA} onPick={onPickA} multiple={domain === "striated"} />
              <FilePick label="Mark B" files={markB} onPick={setMarkB} multiple={domain === "striated"} />
            </div>
            <p className="text-xs text-muted">
              {domain === "striated"
                ? "Each mark is a bullet — select all of its land scans (e.g. 6). A single land is only weakly diagnostic; the strength comes from aggregating the lands."
                : "One breech-face scan per mark."}
            </p>
            <button
              onClick={onCompare}
              disabled={!markA.length || !markB.length || loading}
              className="w-full rounded-lg bg-gradient-to-r from-indigo-500 via-sky-500 to-cyan-400 px-4 py-3 font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "Comparing…" : "Compute likelihood ratio"}
            </button>
            {error && (
              <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-500 dark:text-rose-200">
                {error}
              </p>
            )}
          </section>
        </Reveal>

        {result && (
          <section className="rise mt-8">
            {result.sample && (
              <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/[0.08] px-3 py-1 text-xs text-foreground/80">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                Sample — a precomputed real Hamby-252 same-source comparison
              </p>
            )}
            <ReportView report={result.data} />
          </section>
        )}

        <footer className="mt-16 space-y-3 text-center text-xs leading-relaxed text-muted">
          <p>
            <a
              href="https://api.verity.codes/scalar"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
            >
              API reference ↗
            </a>
          </p>
          <p>
            The representation reports a calibrated likelihood ratio; it never makes the decision.
            <br />
            Not a claim about the error rate of forensic examination, which remains unknown.
          </p>
        </footer>
      </main>
    </>
  );
}
