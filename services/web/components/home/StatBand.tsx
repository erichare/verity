import cmrValidation from "@/lib/cmr-validation.json";

interface Reduction {
  n_km: number;
  n_knm: number;
  source_disjoint: { auc: number; cllr: number };
}
const cmr = cmrValidation as unknown as { reductions: Reduction[] };

// A multi-modal credibility strip: one pipeline, validated source-disjoint across
// every mark type. Sourced from the same committed validation data that feeds the
// /method "three reductions" table, so the hero never drifts from — or contradicts —
// the proof it links to. Not tied to any single modality or the example below it.
function buildStats(): { value: string; label: string }[] {
  const r = cmr.reductions;
  const totalPairs = r.reduce((s, x) => s + x.n_km + x.n_knm, 0);
  const minAuc = Math.min(...r.map((x) => x.source_disjoint.auc));
  return [
    { value: `${r.length}`, label: "Mark types, one pipeline" },
    { value: `${(Math.floor(minAuc * 100) / 100).toFixed(2)}+`, label: "Source-disjoint AUC" },
    { value: totalPairs.toLocaleString("en-US"), label: "Reference pairs" },
    { value: "0", label: "Per-modality re-tuning" },
  ];
}

/**
 * A thin row of real, verifiable numbers. The default is the full stat block; the
 * `compact` variant collapses it to a single dot-separated caption — used as the
 * calibration footing directly under the compare workspace rather than in the hero.
 */
export function StatBand({ className, compact }: { className?: string; compact?: boolean }) {
  const stats = buildStats();
  if (compact) {
    return (
      <p
        className={`flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-center text-xs text-muted ${className ?? ""}`}
      >
        {stats.map((s, i) => (
          <span key={s.label} className="inline-flex items-center gap-2">
            {i > 0 && <span aria-hidden className="text-border">·</span>}
            <span>
              <span className="font-mono font-medium text-foreground/80">{s.value}</span>{" "}
              {s.label.toLowerCase()}
            </span>
          </span>
        ))}
      </p>
    );
  }
  return (
    <dl
      className={`mx-auto grid w-full max-w-3xl grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4 ${className ?? ""}`}
    >
      {stats.map((s) => (
        <div key={s.label} className="flex flex-col items-center text-center">
          <dt className="order-2 mt-0.5 text-[11px] uppercase tracking-wider text-muted">{s.label}</dt>
          <dd className="order-1 font-mono text-2xl font-semibold accent-text sm:text-3xl">{s.value}</dd>
        </div>
      ))}
    </dl>
  );
}
