"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { compareMarks, detectDomain, getDomains, type Detection } from "@/lib/api";
import type { CompareResponse } from "@/lib/types";
import { Reveal } from "@/components/Reveal";
import { StatBand } from "@/components/home/StatBand";
import { LiveProof } from "@/components/home/LiveProof";
import { MarkBreadth } from "@/components/home/MarkBreadth";
import { WhyTeaser } from "@/components/home/WhyTeaser";
import { SiteNav } from "@/components/SiteNav";
import { Workspace } from "@/components/workspace/Workspace";
import { LabBench } from "@/components/workspace/LabBench";

const HeroSurface = dynamic(() => import("@/components/three/HeroSurface"), {
  ssr: false,
});

const DOMAIN_LABELS: Record<string, string> = {
  impressed: "Impressed — cartridge breech face",
  striated: "Striated — bullet land(s)",
  toolmark: "Toolmark — striated (screwdriver, pry…)",
};

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

export default function Home() {
  const [domains, setDomains] = useState<string[]>([]);
  const [domain, setDomain] = useState("striated");
  const [markA, setMarkA] = useState<File[]>([]);
  const [markB, setMarkB] = useState<File[]>([]);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [uploadKey, setUploadKey] = useState(0);
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
      setResult(await compareMarks(domain, markA, markB));
      setUploadKey((k) => k + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "comparison failed");
    } finally {
      setLoading(false);
    }
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
      {/* Top bar — the shared fixed nav (cinematic scrim variant on the home hero) */}
      <SiteNav cinematic />

      {/* Cinematic hero */}
      <section
        id="top"
        className="relative isolate flex min-h-[92svh] items-center justify-center overflow-hidden px-6 pt-24 sm:pt-0"
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
              href="#compare"
              className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-[#f4f1ea] shadow-lg shadow-[#0e2a47]/20 transition hover:opacity-90"
            >
              Compare two marks ↓
            </a>
            <a
              href="/method"
              className="glass rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
            >
              How it works
            </a>
          </div>
          <p className="mt-4 text-xs text-foreground/60">
            <a href="#upload" className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent">
              or upload your own scans →
            </a>
          </p>
        </div>
      </section>

      {/* Content */}
      <main className="mx-auto mt-6 w-full max-w-4xl px-6 pb-24 sm:-mt-16">
        {/* The compare workspace — the live app, front and center. */}
        <section id="compare" className="scroll-mt-20">
          <div className="mb-5">
            <span className="inline-flex items-center gap-2 rounded-full border border-brass/30 bg-brass/[0.08] px-3 py-1 text-xs font-medium text-foreground/80">
              <span className="h-1.5 w-1.5 rounded-full bg-brass" />
              The live tool
            </span>
            <h2 className="mt-3 font-display text-2xl font-medium text-foreground sm:text-3xl">
              Compare <span className="accent-text">two marks</span>
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-muted">
              Pick two real specimens and watch the calibrated likelihood ratio resolve — no
              file of your own needed. Every gallery result is a real, precomputed comparison;
              to run your own scans, upload them below.
            </p>
          </div>
          <Workspace />
        </section>

        {/* Live proof — the same method, opposite verdicts */}
        <Reveal className="mt-20 sm:mt-28">
          <LiveProof />
        </Reveal>

        {/* Breadth — one pipeline, three mark types */}
        <Reveal className="mt-20 sm:mt-28">
          <MarkBreadth />
        </Reveal>

        {/* Why it was necessary + the scientific contribution */}
        <Reveal className="mt-20 sm:mt-28">
          <WhyTeaser />
        </Reveal>

        {/* Upload-your-own path — the live API, for visitors with their own .x3p scans. */}
        <Reveal className="mt-20 sm:mt-28">
          <div
            id="upload"
            className="scroll-mt-20 rounded-[1.45rem] bg-gradient-to-br from-brass via-primary to-brass p-[1.5px] shadow-2xl shadow-[#0e2a47]/15"
          >
            <section className="space-y-5 rounded-[1.35rem] bg-background p-6 sm:p-8">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/[0.08] px-3 py-1 text-xs font-medium text-foreground/80">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                Upload your own
              </span>
              <h2 className="mt-3 font-display text-2xl font-medium text-foreground sm:text-3xl">
                Bring your <span className="accent-text">own scans</span>
              </h2>
              <p className="mt-2 max-w-2xl text-sm text-muted">
                Have .x3p scans? Compare them live against the deployed engine.
              </p>
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
                : domain === "toolmark"
                  ? "One striated profile scan per toolmark (e.g. a screwdriver mark)."
                  : "One breech-face scan per mark."}
            </p>
            <button
              onClick={onCompare}
              disabled={!markA.length || !markB.length || loading}
              className="w-full rounded-lg bg-primary px-4 py-3 font-semibold text-[#f4f1ea] shadow-lg shadow-[#0e2a47]/20 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? "Comparing…" : "Compute likelihood ratio"}
            </button>
            {error && (
              <p className="rounded-lg border border-oxblood/30 bg-oxblood/10 p-3 text-sm text-oxblood">
                {error}
              </p>
            )}
            </section>
          </div>
        </Reveal>

        {result && (
          <section className="rise mt-8">
            <LabBench
              result={{ report: result, provenance: "upload" }}
              revealKey={`upload-${uploadKey}`}
            />
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
