"use client";

import { useState } from "react";
import type { Stage, StudioRun } from "@/lib/studio";

/**
 * The reading panel beside the stage: the examiner-voice caption for the current step, its
 * live numeric readouts (all real engine values), and a "recipe" drawer exposing the
 * scorer-config hash — the glass-box reproducibility handle.
 */
export function CaseFilePanel({
  run,
  stage,
  total,
}: {
  run: StudioRun;
  stage: Stage;
  total: number;
}) {
  const [recipeOpen, setRecipeOpen] = useState(false);

  return (
    <aside className="flex h-full w-full flex-col gap-4 overflow-y-auto p-5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
          Case file
        </span>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] ${
            run.provenance === "upload"
              ? "border-border bg-foreground/[0.04] text-foreground/70"
              : "border-brass/30 bg-brass/[0.08] text-foreground/70"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              run.provenance === "upload" ? "bg-foreground/50" : "bg-brass"
            }`}
          />
          {run.provenance === "upload" ? "Your scan" : "Curated specimen"}
        </span>
      </div>

      <div>
        <p className="font-mono text-[11px] text-muted">
          {run.aLabel} <span className="text-muted/60">vs</span> {run.bLabel}
        </p>
      </div>

      <div className="border-t border-border pt-4">
        <p className="font-mono text-[10px] uppercase tracking-wider text-brass">
          Step {stage.num} / {total} · {stage.label}
        </p>
        <p className="mt-2 font-display text-lg leading-snug text-foreground">{stage.caption}</p>
        <p className="mt-2 text-sm leading-relaxed text-muted">{stage.why}</p>
      </div>

      <dl className="mt-1 flex flex-col gap-2.5 border-t border-border pt-4 font-mono text-xs">
        {stage.readouts.map((r) => (
          <div key={r.label} className="flex items-baseline justify-between gap-3">
            <dt className="text-muted">{r.label}</dt>
            <dd className="truncate text-right text-foreground">{r.value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-auto border-t border-border pt-3">
        <button
          type="button"
          onClick={() => setRecipeOpen((v) => !v)}
          className="flex w-full items-center gap-2 font-mono text-[10px] text-accent transition hover:opacity-80"
          aria-expanded={recipeOpen}
        >
          <span aria-hidden>{recipeOpen ? "▾" : "▸"}</span> recipe · reproducible
        </button>
        {recipeOpen && (
          <div className="mt-2 space-y-1 font-mono text-[10px] leading-relaxed text-muted">
            <p>
              scorer-config{" "}
              <span className="text-foreground/80">{run.configHash.slice(0, 12)}…</span>
            </p>
            <p>
              reference <span className="text-foreground/80">{run.report.reference.name}</span>
            </p>
            <p className="text-muted/70">
              Every frame derives from this deterministic configuration.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
