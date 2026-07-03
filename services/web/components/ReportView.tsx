import type { ComparisonReport } from "@/lib/types";
import AttributionView from "@/components/AttributionView";
import ScopeNotes, { scopeWarnings } from "@/components/ScopeNotes";
import { LRCounter } from "@/components/workspace/LRCounter";
import { formatLR } from "@/lib/format";

// Evidence semantics: navy authority for strong same-source support, brass for the
// softer same-source grades, oxblood for different-source (exclusion). `accent`
// (navy in light, lifted steel in dark) keeps the strong badge legible in both modes.
function strengthColor(verbal: string, supportsSame: boolean): string {
  if (!supportsSame)
    return "bg-oxblood/12 text-oxblood border-oxblood/30";
  if (verbal.includes("no meaningful"))
    return "bg-foreground/10 text-muted border-border";
  if (verbal.includes("weak"))
    return "bg-brass/12 text-brass-text border-brass/30";
  if (verbal.includes("moderate"))
    return "bg-brass/15 text-brass-text border-brass/35";
  return "bg-accent/12 text-accent border-accent/35";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-muted">{label}</span>
      <span className="font-mono text-sm text-foreground/90">{value}</span>
    </div>
  );
}

export default function ReportView({
  report,
  animateIn = false,
  showAttribution = true,
}: {
  report: ComparisonReport;
  animateIn?: boolean;
  showAttribution?: boolean;
}) {
  const supportsSame = report.log10_lr > 0;
  const bound = report.lr_bound_log10;
  const frac = bound ? Math.min(1, Math.abs(report.log10_lr) / bound) : 0;
  const warnings = scopeWarnings(report.scope);

  return (
    <div className="glass space-y-6 rounded-2xl p-6 sm:p-8">
      {report.evidence_note?.single_land && (
        <div className="flex gap-2 rounded-lg border border-amber-400/30 bg-amber-400/[0.08] p-3 text-sm leading-relaxed text-amber-800 dark:text-amber-200">
          <span aria-hidden className="select-none">⚠</span>
          <p>
            <strong className="font-semibold">Diagnostic only.</strong> {report.evidence_note.reason}
          </p>
        </div>
      )}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted">Likelihood ratio</p>
          <p className="leading-none">
            <LRCounter
              value={report.likelihood_ratio}
              animate={animateIn}
              className={`font-mono text-5xl font-semibold ${supportsSame ? "accent-text" : "text-oxblood"}`}
            />
          </p>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-foreground/80">
            The observed similarity is{" "}
            <strong className="text-foreground">
              {formatLR(supportsSame ? report.likelihood_ratio : 1 / report.likelihood_ratio)}×
            </strong>{" "}
            more probable if the marks share a source than if they do not
            {supportsSame ? "" : " — i.e. support for different sources"}.
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-sm font-medium ${strengthColor(report.verbal, supportsSame)}`}>
          {report.verbal}
        </span>
      </div>

      {bound !== null && (
        <div>
          <div className="mb-1.5 flex justify-between text-xs text-muted">
            <span>
              log₁₀ LR = {report.log10_lr.toFixed(2)}
              {report.log10_lr_ci_lo != null && report.log10_lr_ci_hi != null && (
                <span className="text-foreground/70">
                  {" "}· 95% CI [{report.log10_lr_ci_lo.toFixed(2)}, {report.log10_lr_ci_hi.toFixed(2)}]
                  {report.n_sources ? ` across ${report.n_sources} sources` : ""}
                </span>
              )}
            </span>
            <span>bound ±{bound.toFixed(2)} (reference size)</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <div
              className={`h-full rounded-full ${supportsSame ? "bg-gradient-to-r from-primary to-brass" : "bg-oxblood"}`}
              style={{ width: `${Math.max(2, frac * 100)}%` }}
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-5 border-t border-border pt-5 sm:grid-cols-4">
        <Stat label="Domain" value={report.domain} />
        <Stat label="Scorer" value={report.score_kind} />
        <Stat label="Score" value={report.score.toFixed(3)} />
        <Stat label="Reference AUC" value={report.reference.auc.toFixed(3)} />
        <Stat label="Reference Cllr" value={report.reference.cllr.toFixed(3)} />
        <Stat label="Cllr min" value={report.reference.cllr_min.toFixed(3)} />
        <Stat label="KM / KNM" value={`${report.reference.n_km} / ${report.reference.n_knm}`} />
        <Stat label="Reference" value={report.reference.name} />
      </div>

      {showAttribution && report.previews && report.attribution.length > 0 && (
        <AttributionView
          previews={report.previews}
          regions={report.attribution}
          regionsB={report.attribution_b}
          domain={report.domain}
        />
      )}

      {warnings.length > 0 && (
        <div className="rounded-lg border border-amber-400/25 bg-amber-400/[0.05] p-3">
          <p className="mb-2 text-[10px] uppercase tracking-wider text-amber-700/80 dark:text-amber-300/80">
            Applicability warnings — the comparison proceeded, but note:
          </p>
          <ScopeNotes warnings={warnings} />
        </div>
      )}

      <p className="rounded-lg border border-border bg-foreground/[0.03] p-3 text-sm italic leading-relaxed text-muted">
        {report.scope_note}
      </p>
    </div>
  );
}
