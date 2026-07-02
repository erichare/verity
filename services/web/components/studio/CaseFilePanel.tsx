"use client";

import { useEffect, useState } from "react";
import { getScorerConfig } from "@/lib/stepApi";
import type { Stage, StudioRun } from "@/lib/studio";

// The deployed engine's scorer-config hash, fetched once (best-effort — null on failure).
// Uploads score against the live engine, so their recipe must show THIS hash, not the baked
// tour's; on the tour a differing live hash is surfaced as config drift.
let liveHashPromise: Promise<string | null> | null = null;
function fetchLiveHash(): Promise<string | null> {
  liveHashPromise ??= getScorerConfig().then((c) => c?.config_hash ?? null);
  return liveHashPromise;
}

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
  const [liveHash, setLiveHash] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchLiveHash().then((h) => {
      if (alive) setLiveHash(h);
    });
    return () => {
      alive = false;
    };
  }, []);

  // Uploads: the live engine's hash (fall back to the baked one if the fetch failed).
  // Tour: always the baked hash the numbers were generated under, plus a drift note.
  const isUpload = run.provenance === "upload";
  const shownHash = isUpload && liveHash ? liveHash : run.configHash;
  const drifted = !isUpload && liveHash != null && liveHash !== run.configHash;

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
              scorer-config <span className="text-foreground/80">{shownHash.slice(0, 12)}…</span>
              {isUpload && liveHash && <span className="text-muted/70"> (live engine)</span>}
            </p>
            <p>
              reference <span className="text-foreground/80">{run.report.reference.name}</span>
            </p>
            <p className="text-muted/70">
              Every frame derives from this deterministic configuration.
            </p>
          </div>
        )}
        {drifted && (
          <p className="mt-2 font-mono text-[10px] leading-relaxed text-oxblood">
            config drift: the live engine runs {liveHash.slice(0, 12)}… — this tour was baked
            under {run.configHash.slice(0, 12)}….
          </p>
        )}
      </div>
    </aside>
  );
}
