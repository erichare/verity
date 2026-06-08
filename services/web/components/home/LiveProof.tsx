"use client";

import { useState } from "react";
import methodData from "@/lib/method-data.json";
import { formatLRx } from "@/lib/format";
import { AlignedSignatures } from "@/components/method/AlignedSignatures";

interface Band {
  x_frac: number;
  w_frac: number;
}
interface Example {
  sublabel: string;
  signatureA: number[];
  signatureB: number[];
  bandsA: Band[];
  bandsB: Band[];
  lr: number;
  verbal: string;
}
interface CalibrationSlice {
  auc: number;
  cllr: number;
  nKm: number;
  nKnm: number;
}
const data = methodData as unknown as { km: Example; knm: Example; calibration: CalibrationSlice };

/**
 * The single most persuasive thing on the site, brought to the homepage: the
 * SAME algorithm flipping between same-source and different-source verdicts on
 * real Hamby-252 bullets. Reuses the real method-data and the AlignedSignatures
 * visualization — no fabricated numbers.
 */
export function LiveProof() {
  const [mode, setMode] = useState<"km" | "knm">("km");
  const ex = data[mode];
  const cal = data.calibration;
  const positive = ex.lr >= 1;
  const nRegions = Math.min(ex.bandsA.length, ex.bandsB.length);

  return (
    <section id="proof" className="scroll-mt-24">
      <div className="text-center">
        <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          A real comparison, live
        </span>
        <h2 className="mt-5 font-display text-3xl font-medium text-foreground sm:text-4xl">
          One method, <span className="accent-text">opposite conclusions</span>
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-foreground/80 sm:text-base">
          Two Hamby-252 bullets fired from the <em>same</em> barrel, and two from{" "}
          <em>different</em> barrels — the same algorithm, with zero parameters tuned to these
          bullets. Flip the switch and watch the weight of evidence reverse.
        </p>
      </div>

      <div className="glass mt-6 rounded-2xl p-5 sm:p-8">
        <div className="flex justify-center">
          <div className="inline-flex rounded-full border border-border bg-foreground/[0.03] p-1 text-sm">
            {(["km", "knm"] as const).map((k) => (
              <button
                key={k}
                onClick={() => setMode(k)}
                aria-pressed={mode === k}
                className={`rounded-full px-4 py-1.5 font-medium transition ${
                  mode === k
                    ? "bg-gradient-to-r from-indigo-500 to-cyan-400 text-slate-950"
                    : "text-foreground/70 hover:text-foreground"
                }`}
              >
                {k === "km" ? "Same firearm" : "Different firearms"}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-6 grid gap-6 sm:grid-cols-[0.85fr_1.15fr] sm:items-center">
          <div>
            <p className="text-xs uppercase tracking-wider text-muted">{ex.sublabel}</p>
            <p
              className={`mt-1 font-mono text-5xl font-semibold sm:text-6xl ${
                positive ? "accent-text" : "text-rose-500 dark:text-rose-300"
              }`}
            >
              {formatLRx(ex.lr)}
            </p>
            <p className="mt-3 text-sm leading-relaxed text-foreground/80">
              {ex.verbal}. The reference can support at most{" "}
              <strong className="text-foreground">{cal.nKm}:1</strong> either way — and the same
              code produced this with nothing tuned to these bullets.
            </p>
          </div>

          <div className="overflow-hidden rounded-xl border border-border bg-foreground/[0.02] p-3">
            <AlignedSignatures
              a={ex.signatureA}
              b={ex.signatureB}
              bandsA={ex.bandsA}
              bandsB={ex.bandsB}
              className="h-44 sm:h-48"
            />
            <p className="mt-1 px-1 text-xs text-muted">
              {nRegions} congruent matching {nRegions === 1 ? "region" : "regions"} —{" "}
              <span style={{ color: "var(--accent)" }}>mark A</span> vs{" "}
              <span style={{ color: "var(--accent-2)" }}>mark B</span>
            </p>
          </div>
        </div>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-xs text-muted">
          <span>
            {cal.nKm} same-source · {cal.nKnm} different-source reference pairs · AUC{" "}
            {cal.auc.toFixed(3)} · Cllr {cal.cllr.toFixed(3)}
          </span>
          <a href="/method" className="text-foreground/70 transition hover:text-accent">
            See the full six-step walkthrough →
          </a>
        </div>
      </div>
    </section>
  );
}
