"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { compareMarks, detectDomain, getDomains, type Detection } from "@/lib/api";
import type { CompareResponse } from "@/lib/types";
import { FilePick } from "@/components/FilePick";
import { Reveal } from "@/components/Reveal";
import { StatBand } from "@/components/home/StatBand";
import { AppNav } from "@/components/app/AppNav";
import { SiteFooter } from "@/components/SiteFooter";
import { Workspace } from "@/components/workspace/Workspace";
import { LabBench } from "@/components/workspace/LabBench";
import { JsonLd, organizationJsonLd } from "@/components/seo/JsonLd";
import { LinkArrow } from "@/components/LinkArrow";

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
  const uploadResultRef = useRef<HTMLElement>(null);

  useEffect(() => {
    getDomains().then((d) => {
      if (d.length) {
        setDomains(d);
        setDomain((cur) => (d.includes(cur) ? cur : d[0]));
      }
    });
  }, []);

  useEffect(() => {
    if (result) uploadResultRef.current?.focus();
  }, [result]);

  async function onCompare(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
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

  const shownDomains = domains.length ? domains : ["striated", "impressed", "toolmark"];

  return (
    <>
      {/* Top bar — the shared fixed nav */}
      <AppNav />
      {/* Organization + WebSite entity signals for search engines (server-rendered). */}
      <JsonLd data={organizationJsonLd} />

      {/* The primary landmark wraps the hero (with the page h1) through the content.
          The footer is intentionally rendered after </main>, outside the landmark. */}
      <main id="main">
      {/* Hero — clean paper canvas + the faint ledger grid from the body */}
      <section
        id="top"
        className="relative flex items-center justify-center px-6 pb-14 pt-24 sm:min-h-[72svh] sm:pb-12 sm:pt-24"
      >
        <div className="rise mx-auto max-w-3xl text-center">
          <p className="mb-5 text-[11px] font-semibold uppercase tracking-[0.18em] text-brass-text">
            Open-source research preview
          </p>
          <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-7xl">
            Forensic marks, <span className="accent-text">weighed as evidence</span>.
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-foreground/80 sm:text-xl">
            Compare real specimens — or upload X3P scans — and get an auditable{" "}
            <strong className="text-foreground">likelihood ratio, uncertainty, and a map of the regions
            that drove it</strong>. Never a black-box &ldquo;match.&rdquo;
          </p>
          <p className="mx-auto mt-4 max-w-xl text-xs leading-relaxed text-foreground/70">
            Verity reports the weight of evidence. It never makes the decision, and it does not claim
            an examination error rate.
          </p>

          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <a
              href="#compare"
              className="inline-flex min-h-11 items-center rounded-full bg-primary px-6 py-3 text-sm font-semibold text-[#f4f1ea] shadow-lg shadow-[#0e2a47]/20 transition hover:opacity-90"
            >
              Try a real example<LinkArrow className="ml-1.5" />
            </a>
            <a
              href="#upload"
              className="glass inline-flex min-h-11 items-center rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
            >
              Upload X3P scans<LinkArrow className="ml-1.5" />
            </a>
          </div>
          <p className="mt-4 text-xs text-muted">
            No file needed for the example ·{" "}
            <a
              href="https://docs.verity.codes/method"
              className="font-medium text-foreground/75 underline decoration-border underline-offset-4 transition hover:text-foreground hover:decoration-accent"
            >
              Read the method<LinkArrow kind="external" className="ml-1" />
            </a>
          </p>
        </div>
      </section>

      <section aria-labelledby="validation-at-a-glance" className="mx-auto w-full max-w-4xl px-6">
        <div className="glass rounded-2xl px-5 py-5 shadow-lg shadow-[#0e2a47]/[0.04] sm:px-7">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2
              id="validation-at-a-glance"
              className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted"
            >
              Validation at a glance
            </h2>
            <a
              href="https://docs.verity.codes/method"
              className="text-xs font-medium text-foreground/70 transition hover:text-foreground"
            >
              See the methodology<LinkArrow kind="external" className="ml-1" />
            </a>
          </div>
          <StatBand className="mt-5" />
        </div>
      </section>

      {/* Content */}
      <div className="mx-auto mt-16 w-full max-w-4xl px-6 pb-24 sm:mt-20">
        {/* The compare workspace — the live app, front and center. */}
        <section id="compare" className="scroll-mt-20">
          <div className="mb-5">
            <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
              Compare <span className="accent-text">two marks</span>
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
              Choose two real specimens — no upload required — and follow the evidence from matched
              regions to the reference population to a calibrated likelihood ratio. Every example is
              a real, precomputed comparison across bullets, cartridge cases, and toolmarks.
            </p>
          </div>
          <Workspace />
        </section>

        {/* Why this exists — one line; the full scientific argument lives on docs.verity.codes */}
        <Reveal className="mt-20 sm:mt-28">
          <div className="text-center">
            <p className="mx-auto max-w-2xl text-sm leading-relaxed text-foreground/70">
              Forensic mark comparison is used in criminal courts yet has no characterized error
              rate. Verity returns a calibrated likelihood ratio with a quantified cost and
              region-level attribution — one method across striated, impressed, and toolmark marks.
            </p>
            <a
              href="https://docs.verity.codes/why"
              className="glass mt-5 inline-flex min-h-11 items-center rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
            >
              Why this exists<LinkArrow className="ml-1" />
            </a>
          </div>
        </Reveal>

        {/* Upload-your-own path — the live API, for visitors with their own .x3p scans. */}
        <Reveal className="mt-20 sm:mt-28">
          <div
            id="upload"
            className="scroll-mt-20 rounded-[1.45rem] bg-gradient-to-br from-brass via-primary to-brass p-[1.5px] shadow-2xl shadow-[#0e2a47]/15"
          >
            <form
              onSubmit={onCompare}
              aria-busy={loading}
              className="space-y-5 rounded-[1.35rem] bg-background p-6 sm:p-8"
            >
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
                className="min-h-11 w-full rounded-lg border border-control bg-background/60 px-3 py-2 text-sm text-foreground outline-none focus:border-accent focus-visible:ring-2 focus-visible:ring-accent"
              >
                {shownDomains.map((d) => (
                  <option key={d} value={d}>
                    {DOMAIN_LABELS[d] ?? d}
                  </option>
                ))}
              </select>
            </div>
            {detected && (
              <p role="status" className="text-xs text-muted">
                Auto-detected from your scan:{" "}
                <span className="text-foreground/80">{DOMAIN_LABELS[detected.domain] ?? detected.domain}</span>
                {" "}— change it above if it&rsquo;s wrong.
              </p>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FilePick
                key={`${domain}-mark-a`}
                label="Mark A"
                files={markA}
                onPick={onPickA}
                multiple={domain === "striated"}
              />
              <FilePick
                key={`${domain}-mark-b`}
                label="Mark B"
                files={markB}
                onPick={setMarkB}
                multiple={domain === "striated"}
              />
            </div>
            <div className="space-y-2 rounded-lg bg-foreground/[0.035] p-3 text-xs leading-relaxed text-muted">
              <p>
                <strong className="font-medium text-foreground/80">Private by design.</strong> Your first
                Mark A scan is sent to{" "}
                <span className="font-mono text-foreground/70">api.verity.codes</span> to detect the mark
                type when you pick it; both marks are sent when you compute the likelihood ratio.
                Nothing is stored after the response.
              </p>
              <p>
                {domain === "striated"
                  ? "For each bullet, select all land scans (typically 6). A single land is only weakly diagnostic; the strength comes from aggregating the lands."
                  : domain === "toolmark"
                    ? "Select one striated profile scan per toolmark (for example, a screwdriver mark)."
                    : "Select one breech-face scan per mark."}
              </p>
            </div>
            <p className="sr-only" role="status" aria-live="polite">
              {loading
                ? "Comparing the selected marks."
                : result
                  ? "Comparison complete. The detailed result follows the upload form."
                  : ""}
            </p>
            <button
              type="submit"
              disabled={!markA.length || !markB.length || loading}
              className="min-h-12 w-full rounded-lg bg-primary px-4 py-3 font-semibold text-[#f4f1ea] shadow-lg shadow-[#0e2a47]/20 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading
                ? "Comparing…"
                : markA.length && markB.length
                  ? "Compute likelihood ratio"
                  : "Select both marks to compare"}
            </button>
            {error && (
              <p role="alert" className="rounded-lg border border-oxblood/30 bg-oxblood/10 p-3 text-sm text-oxblood">
                {error}
              </p>
            )}
            </form>
          </div>
        </Reveal>

        {result && (
          <section
            ref={uploadResultRef}
            tabIndex={-1}
            aria-labelledby="upload-result-heading"
            className="rise mt-8 rounded-2xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brass"
          >
            <h2 id="upload-result-heading" className="sr-only">
              Uploaded mark comparison result
            </h2>
            <LabBench
              result={{ report: result, provenance: "upload" }}
              revealKey={`upload-${uploadKey}`}
            />
          </section>
        )}

      </div>
      </main>

      {/* Shared trust chrome — GitHub, license, white paper, About, and the five-host
          map. It carries the calibrated-LR / error-rate disclaimer that used to live in
          the inline footer here. */}
      <SiteFooter />
    </>
  );
}
