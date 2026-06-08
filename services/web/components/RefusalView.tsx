import type { RefusalResponse } from "@/lib/types";
import ScopeNotes, { scopeWarnings } from "@/components/ScopeNotes";

export default function RefusalView({ result }: { result: RefusalResponse }) {
  const all = scopeWarnings(result.scope);
  const blocking = all.filter((w) => w.check.severity === "refuse");
  const shown = blocking.length > 0 ? blocking : all;

  return (
    <div className="glass space-y-5 rounded-2xl border-rose-400/30 p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-rose-500/80">Out of scope</p>
          <p className="mt-1 text-2xl font-semibold text-foreground">
            No likelihood ratio reported
          </p>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-foreground/80">{result.reason}</p>
        </div>
        <span className="rounded-full border border-rose-400/30 bg-rose-400/15 px-3 py-1 text-sm font-medium text-rose-700 dark:text-rose-200">
          refused
        </span>
      </div>

      {shown.length > 0 && (
        <div className="border-t border-border pt-4">
          <p className="mb-2 text-[10px] uppercase tracking-wider text-muted">
            Applicability checks
          </p>
          <ScopeNotes warnings={shown} />
        </div>
      )}

      <p className="rounded-lg border border-border bg-foreground/[0.03] p-3 text-sm italic leading-relaxed text-muted">
        {result.scope_note}
      </p>
    </div>
  );
}
