import type { ComparisonReport } from "@/lib/types";
import AttributionView from "@/components/AttributionView";
import { formatLR } from "@/lib/format";

function strengthColor(verbal: string): string {
  if (verbal.includes("no meaningful"))
    return "bg-slate-500/15 text-slate-600 dark:text-slate-300 border-slate-500/25";
  if (verbal.includes("weak"))
    return "bg-amber-400/15 text-amber-700 dark:text-amber-200 border-amber-400/30";
  if (verbal.includes("moderate"))
    return "bg-sky-400/15 text-sky-700 dark:text-sky-200 border-sky-400/30";
  return "bg-emerald-400/15 text-emerald-700 dark:text-emerald-200 border-emerald-400/30";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-muted">{label}</span>
      <span className="font-mono text-sm text-foreground/90">{value}</span>
    </div>
  );
}

export default function ReportView({ report }: { report: ComparisonReport }) {
  const supportsSame = report.log10_lr > 0;
  const bound = report.lr_bound_log10;
  const frac = bound ? Math.min(1, Math.abs(report.log10_lr) / bound) : 0;

  return (
    <div className="glass space-y-6 rounded-2xl p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted">Likelihood ratio</p>
          <p className="accent-text font-mono text-5xl font-semibold">
            {formatLR(report.likelihood_ratio)}
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
        <span className={`rounded-full border px-3 py-1 text-sm font-medium ${strengthColor(report.verbal)}`}>
          {report.verbal}
        </span>
      </div>

      {bound !== null && (
        <div>
          <div className="mb-1.5 flex justify-between text-xs text-muted">
            <span>
              log₁₀ LR = {report.log10_lr.toFixed(2)}
              {report.log10_lr_ci_lo != null && report.log10_lr_ci_hi != null && (
                <span className="text-foreground/50">
                  {" "}· 95% CI [{report.log10_lr_ci_lo.toFixed(2)}, {report.log10_lr_ci_hi.toFixed(2)}]
                </span>
              )}
            </span>
            <span>bound ±{bound.toFixed(2)} (reference size)</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-foreground/10">
            <div
              className={`h-full rounded-full ${supportsSame ? "bg-gradient-to-r from-sky-500 to-emerald-400" : "bg-gradient-to-r from-rose-500 to-rose-400"}`}
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

      {report.previews && report.attribution.length > 0 && (
        <AttributionView
          previews={report.previews}
          regions={report.attribution}
          regionsB={report.attribution_b}
          domain={report.domain}
        />
      )}

      <p className="rounded-lg border border-border bg-foreground/[0.03] p-3 text-sm italic leading-relaxed text-muted">
        {report.scope_note}
      </p>
    </div>
  );
}
