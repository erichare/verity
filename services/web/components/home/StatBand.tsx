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

/** A thin row of real, verifiable numbers — the credibility the hero was missing. */
export function StatBand({ className }: { className?: string }) {
  const stats = buildStats();
  return (
    <dl
      className={`mx-auto flex max-w-2xl flex-wrap items-stretch justify-center gap-x-8 gap-y-4 ${className ?? ""}`}
    >
      {stats.map((s) => (
        <div key={s.label} className="flex flex-col items-center text-center">
          <dt className="font-mono text-2xl font-semibold accent-text sm:text-3xl">{s.value}</dt>
          <dd className="mt-0.5 text-[11px] uppercase tracking-wider text-muted">{s.label}</dd>
        </div>
      ))}
    </dl>
  );
}
