"use client";

import { useEffect, useState } from "react";
import { compareMarks, detectDomain, getDomains, type Detection } from "@/lib/api";
import type { CompareResponse } from "@/lib/types";
import { FilePick } from "@/components/FilePick";
import { Reveal } from "@/components/Reveal";
import { StatBand } from "@/components/home/StatBand";
import { AppNav } from "@/components/app/AppNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Workspace } from "@/components/workspace/Workspace";
import { LabBench } from "@/components/workspace/LabBench";

const DOMAIN_LABELS: Record<string, string> = {
  impressed: "Impressed — cartridge breech face",
  striated: "Striated — bullet land(s)",
  toolmark: "Toolmark — striated (screwdriver, pry…)",
};

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
      {/* Top bar — the shared fixed nav */}
      <AppNav />

      {/* Hero — clean paper canvas + the faint ledger grid from the body */}
      <section
        id="top"
        className="relative flex min-h-[72svh] items-center justify-center px-6 pt-28 sm:pt-24"
      >
        <div className="rise mx-auto max-w-3xl text-center">
          <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-7xl">
            Forensic marks, <span className="accent-text">weighed as evidence</span>.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-foreground/80 sm:text-xl">
            One calibrated, explainable method for comparing forensic surface marks — a{" "}
            <strong className="text-foreground">likelihood ratio with a characterized cost</strong>, and a
            map of <strong className="text-foreground">exactly which regions drove the match</strong>.
          </p>
          <p className="mx-auto mt-4 max-w-xl text-xs leading-relaxed text-foreground/70">
            It reports the weight of evidence — it never makes the decision, and makes no claim about
            the error rate of examination.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
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
        </div>
      </section>

      {/* Content */}
      <main className="mx-auto mt-6 w-full max-w-4xl px-6 pb-24">
        {/* The compare workspace — the live app, front and center. */}
        <section id="compare" className="scroll-mt-20">
          <div className="mb-5">
            <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
              Compare <span className="accent-text">two marks</span>
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-muted">
              Pick two real specimens — bullets, cartridge cases, or toolmarks — and watch the
              calibrated likelihood ratio resolve, no file of your own needed. One pipeline, zero
              per-modality tuning; every result is a real, precomputed comparison. To run your own
              scans, upload them below.
            </p>
          </div>
          <Workspace />
          <StatBand compact className="mt-6" />
        </section>

        {/* Why this exists — one line; the full scientific argument lives on docs.verity.codes */}
        <Reveal className="mt-28 sm:mt-40">
          <div className="text-center">
            <p className="mx-auto max-w-2xl text-sm leading-relaxed text-foreground/70">
              Forensic mark comparison is used in criminal courts yet has no characterized error
              rate. Verity returns a calibrated likelihood ratio with a quantified cost and
              region-level attribution — one method across striated and impressed marks.
            </p>
            <a
              href="/why"
              className="glass mt-5 inline-block rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
            >
              Why this exists →
            </a>
          </div>
        </Reveal>

        {/* Upload-your-own path — the live API, for visitors with their own .x3p scans. */}
        <Reveal className="mt-28 sm:mt-40">
          <div
            id="upload"
            className="scroll-mt-20 rounded-[1.45rem] bg-gradient-to-br from-brass via-primary to-brass p-[1.5px] shadow-2xl shadow-[#0e2a47]/15"
          >
            <section className="space-y-5 rounded-[1.35rem] bg-background p-6 sm:p-8">
            <div>
              <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
                Bring your <span className="accent-text">own scans</span>
              </h2>
              <p className="mt-2 max-w-2xl text-sm text-muted">
                Have .x3p scans? Compare them live against the deployed engine.
              </p>
              <p className="mt-1.5 text-xs text-muted">
                See what you get:{" "}
                <a
                  href="/sample-comparison-report.pdf"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
                >
                  sample comparison report (PDF)
                </a>
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <label htmlFor="upload-mark-type" className="text-sm font-medium text-foreground/80">
                Mark type
              </label>
              <select
                id="upload-mark-type"
                value={domain}
                onChange={(e) => {
                  setDomain(e.target.value);
                  setManualDomain(true);
                  setDetected(null);
                  setMarkA([]);
                  setMarkB([]);
                  setResult(null);
                }}
                className="w-full rounded-lg border border-border bg-background/60 px-3 py-2 text-sm text-foreground outline-none focus:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent"
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

      </main>

      {/* Shared trust chrome — GitHub, license, white paper, About, and the five-host
          map. It carries the calibrated-LR / error-rate disclaimer that used to live in
          the inline footer here. */}
      <SiteFooter />
    </>
  );
}
