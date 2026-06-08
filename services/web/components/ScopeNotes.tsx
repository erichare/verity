import type { CompareScope, ScopeCheck, ScopeReport } from "@/lib/types";

export interface ScopeWarning {
  mark: string;
  check: ScopeCheck;
}

// Flatten the per-input scope reports into a list of failed-check advisories.
export function scopeWarnings(scope?: CompareScope): ScopeWarning[] {
  if (!scope) return [];
  const groups: [string, ScopeReport[]][] = [
    ["Mark A", scope.mark_a ?? []],
    ["Mark B", scope.mark_b ?? []],
  ];
  const out: ScopeWarning[] = [];
  for (const [label, reports] of groups) {
    reports.forEach((report, i) => {
      const tag = reports.length > 1 ? `${label} · scan ${i + 1}` : label;
      for (const check of report.checks) {
        if (!check.passed) out.push({ mark: tag, check });
      }
    });
  }
  return out;
}

export default function ScopeNotes({ warnings }: { warnings: ScopeWarning[] }) {
  if (warnings.length === 0) return null;
  return (
    <ul className="space-y-1.5">
      {warnings.map((w, i) => (
        <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
          <span className="font-mono text-[11px] uppercase tracking-wide text-muted">
            {w.mark} · {w.check.name}
          </span>
          <span className="text-foreground/80">{w.check.reason}</span>
        </li>
      ))}
    </ul>
  );
}
