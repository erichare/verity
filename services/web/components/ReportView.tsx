import type { ComparisonReport } from "@/lib/types";

function formatLR(lr: number): string {
  if (lr >= 1) return lr >= 100 ? lr.toExponential(1) : lr.toFixed(1);
  return `${lr.toExponential(1)} (1 / ${(1 / lr).toFixed(1)})`;
}

function strengthColor(verbal: string): string {
  if (verbal.includes("no meaningful")) return "bg-slate-100 text-slate-700";
  if (verbal.includes("weak")) return "bg-amber-100 text-amber-800";
  if (verbal.includes("moderate")) return "bg-sky-100 text-sky-800";
  return "bg-emerald-100 text-emerald-800";
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      <span className="font-mono text-sm text-slate-800">{value}</span>
    </div>
  );
}

export default function ReportView({ report }: { report: ComparisonReport }) {
  const supportsSame = report.log10_lr > 0;
  const bound = report.lr_bound_log10;
  const frac = bound ? Math.min(1, Math.abs(report.log10_lr) / bound) : 0;

  return (
    <div className="space-y-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400">Likelihood ratio</p>
          <p className="font-mono text-4xl font-semibold text-slate-900">
            {formatLR(report.likelihood_ratio)}
          </p>
          <p className="mt-1 text-sm text-slate-600">
            The observed similarity is{" "}
            <strong>{formatLR(supportsSame ? report.likelihood_ratio : 1 / report.likelihood_ratio)}×</strong>{" "}
            more probable if the marks share a source than if they do not
            {supportsSame ? "" : " — i.e. support for different sources"}.
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-sm font-medium ${strengthColor(report.verbal)}`}>
          {report.verbal}
        </span>
      </div>

      {bound !== null && (
        <div>
          <div className="mb-1 flex justify-between text-xs text-slate-400">
            <span>log₁₀ LR = {report.log10_lr.toFixed(2)}</span>
            <span>bound ±{bound.toFixed(2)} (reference size)</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className={`h-full ${supportsSame ? "bg-emerald-500" : "bg-rose-500"}`}
              style={{ width: `${frac * 100}%` }}
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 sm:grid-cols-4">
        <Stat label="Domain" value={report.domain} />
        <Stat label="Scorer" value={report.score_kind} />
        <Stat label="Score" value={report.score.toFixed(3)} />
        <Stat label="Reference AUC" value={report.reference.auc.toFixed(3)} />
        <Stat label="Reference Cllr" value={report.reference.cllr.toFixed(3)} />
        <Stat label="Cllr_min" value={report.reference.cllr_min.toFixed(3)} />
        <Stat label="KM / KNM" value={`${report.reference.n_km} / ${report.reference.n_knm}`} />
        <Stat label="Reference" value={report.reference.name} />
      </div>

      <p className="rounded-lg bg-slate-50 p-3 text-sm italic text-slate-600">{report.scope_note}</p>
    </div>
  );
}
