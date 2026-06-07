"use client";

import { useEffect, useState } from "react";
import { compareMarks, getDomains } from "@/lib/api";
import type { ComparisonReport } from "@/lib/types";
import ReportView from "@/components/ReportView";

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
    <label className="flex cursor-pointer flex-col gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 text-sm transition hover:border-slate-400">
      <span className="font-medium text-slate-700">{label}</span>
      <span className="truncate text-slate-500">{file ? file.name : "Choose an .x3p scan…"}</span>
      <input
        type="file"
        accept=".x3p"
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}

export default function Home() {
  const [domains, setDomains] = useState<string[]>([]);
  const [domain, setDomain] = useState("impressed");
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

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Verity</h1>
        <p className="mt-1 text-slate-500">
          Calibrated, domain-general comparison of forensic surface marks — a transparent
          weight of evidence with a characterized cost.
        </p>
      </header>

      <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-slate-700">Mark type</label>
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
          >
            {(domains.length ? domains : ["impressed"]).map((d) => (
              <option key={d} value={d}>
                {d === "impressed" ? "Impressed (cartridge breech face)" : d}
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
          className="w-full rounded-lg bg-slate-900 px-4 py-2.5 font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {loading ? "Comparing…" : "Compare"}
        </button>
        {error && <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      </section>

      {report && (
        <section className="mt-8">
          <ReportView report={report} />
        </section>
      )}

      <footer className="mt-12 text-center text-xs text-slate-400">
        The neural/statistical layer reports a calibrated likelihood ratio; it does not make the
        decision. Not a claim about the error rate of forensic examination.
      </footer>
    </main>
  );
}
