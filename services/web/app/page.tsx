"use client";

import { useEffect, useState } from "react";
import { compareMarks, getDomains } from "@/lib/api";
import type { ComparisonReport } from "@/lib/types";
import ReportView from "@/components/ReportView";

const DOMAIN_LABELS: Record<string, string> = {
  impressed: "Impressed — cartridge breech face",
  striated: "Striated — bullet land / toolmark",
};

function FilePick({
  label,
  file,
  onPick,
}: {
  label: string;
  file: File | null;
  onPick: (f: File | null) => void;
}) {
  return (
    <label className="group flex cursor-pointer flex-col gap-1.5 rounded-xl border border-dashed border-white/15 bg-white/[0.03] p-4 text-sm transition hover:border-cyan-400/50 hover:bg-white/[0.06]">
      <span className="font-medium text-slate-200">{label}</span>
      <span className="truncate text-slate-400 group-hover:text-slate-300">
        {file ? file.name : "Choose an .x3p scan…"}
      </span>
      <input
        type="file"
        accept=".x3p"
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

function Citations() {
  const refs: [string, string][] = [
    ["National Research Council (2009)", "Strengthening Forensic Science in the United States: A Path Forward."],
    ["PCAST (2016)", "Forensic Science in Criminal Courts: Ensuring Scientific Validity of Feature-Comparison Methods."],
    ["Cuellar, Vanderplas, Luby & Rosenblum (2024)", "Methodological problems in every black-box study of forensic firearm comparisons."],
    ["Song (2013)", "Proposed congruent matching cells (CMC) method for ballistic identification."],
    ["Brümmer & du Preez (2006)", "Application-independent evaluation of speaker detection — the Cllr cost."],
  ];
  return (
    <ul className="mt-4 space-y-1.5 text-xs text-slate-400">
      {refs.map(([who, what]) => (
        <li key={who} className="leading-relaxed">
          <span className="text-slate-300">{who}</span> — <span className="italic">{what}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Home() {
  const [domains, setDomains] = useState<string[]>([]);
  const [domain, setDomain] = useState("striated");
  const [markA, setMarkA] = useState<File | null>(null);
  const [markB, setMarkB] = useState<File | null>(null);
  const [report, setReport] = useState<ComparisonReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDomains().then((d) => {
      if (d.length) {
        setDomains(d);
        setDomain((cur) => (d.includes(cur) ? cur : d[0]));
      }
    });
  }, []);

  async function onCompare() {
    if (!markA || !markB) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      setReport(await compareMarks(domain, markA, markB));
    } catch (e) {
      setError(e instanceof Error ? e.message : "comparison failed");
    } finally {
      setLoading(false);
    }
  }

  const shownDomains = domains.length ? domains : ["striated", "impressed"];

  return (
    <main className="mx-auto w-full max-w-4xl px-6 py-16 sm:py-24">
      {/* Hero */}
      <header className="rise text-center">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-slate-300">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
          Open-science forensic surface comparison
        </span>
        <h1 className="mt-6 text-6xl font-semibold tracking-tight sm:text-7xl">
          <span className="accent-text">Verity</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg leading-relaxed text-slate-300">
          One calibrated, explainable method for comparing forensic surface marks — a{" "}
          <strong className="text-white">likelihood ratio with a characterized cost</strong>, and a map
          of <strong className="text-white">exactly which regions drove the match</strong>.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-2 text-xs text-slate-300">
          {[
            "Striated · bullets & toolmarks",
            "Impressed · cartridge cases",
            "Calibrated LR + Cllr",
            "Region attribution",
          ].map((t) => (
            <span key={t} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1">
              {t}
            </span>
          ))}
        </div>
      </header>

      {/* Scientific contribution */}
      <section className="glass rise mt-14 rounded-2xl p-6 sm:p-8">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-cyan-300/90">
          The scientific contribution
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-slate-300">
          Two decades of review — the National Research Council&rsquo;s 2009 report and the 2016 PCAST
          report — found that most pattern-evidence disciplines lack demonstrated foundational validity,
          and Cuellar et&nbsp;al. (2024) showed that <em>no</em> discipline has a characterized error
          rate. Existing tools are bespoke to one mark type and stop at an uncalibrated score. Verity
          answers this directly:{" "}
          <strong className="text-slate-100">a single, transparent method</strong> that reports a{" "}
          <strong className="text-slate-100">calibrated likelihood ratio with a quantified cost (Cllr)</strong>{" "}
          and <strong className="text-slate-100">region-level attribution</strong>, spanning striated
          marks (bullets, toolmarks) and impressed marks (cartridge breech faces) by generalizing the
          Congruent Matching Cells method (Song, 2013) to arbitrary toolmarks. The representation only
          produces a score; the reportable decision is a monotone, bounded likelihood ratio — auditable
          no matter how the score was computed.
        </p>
        <Citations />
      </section>

      {/* Comparison tool */}
      <section className="glass rise mt-8 space-y-5 rounded-2xl p-6 sm:p-8">
        <h2 className="text-lg font-medium text-white">Compare two marks</h2>
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-slate-300">Mark type</label>
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="w-full rounded-lg border border-white/10 bg-slate-900/60 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400/60"
          >
            {shownDomains.map((d) => (
              <option key={d} value={d} className="bg-slate-900">
                {DOMAIN_LABELS[d] ?? d}
              </option>
            ))}
          </select>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FilePick label="Mark A" file={markA} onPick={setMarkA} />
          <FilePick label="Mark B" file={markB} onPick={setMarkB} />
        </div>
        <button
          onClick={onCompare}
          disabled={!markA || !markB || loading}
          className="w-full rounded-lg bg-gradient-to-r from-indigo-500 via-sky-500 to-cyan-400 px-4 py-3 font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Comparing…" : "Compute likelihood ratio"}
        </button>
        {error && (
          <p className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
            {error}
          </p>
        )}
      </section>

      {report && (
        <section className="rise mt-8">
          <ReportView report={report} />
        </section>
      )}

      <footer className="mt-16 text-center text-xs leading-relaxed text-slate-500">
        The representation reports a calibrated likelihood ratio; it never makes the decision.
        <br />
        Not a claim about the error rate of forensic examination, which remains unknown.
      </footer>
    </main>
  );
}
