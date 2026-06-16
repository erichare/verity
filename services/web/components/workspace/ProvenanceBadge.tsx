import type { BenchResult } from "@/lib/types";

/**
 * The honesty signal on every result: a curated gallery pick is a precomputed real
 * comparison (brass), a live upload is computed on the API (ink). Generalizes the
 * old sample-only badge so it's accurate per pair.
 */
export function ProvenanceBadge({ result }: { result: BenchResult }) {
  if (result.provenance === "upload") {
    return (
      <span className="inline-flex items-center gap-2 rounded-full border border-border bg-foreground/[0.03] px-3 py-1 text-xs text-foreground/80">
        <span className="h-1.5 w-1.5 rounded-full bg-foreground/50" />
        Your scan — computed live via api.verity.codes
      </span>
    );
  }
  const rel = result.relation === "KNM" ? "different-source" : "same-source";
  const detail = result.source ? ` (${result.source}, ${rel})` : "";
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-brass/30 bg-brass/[0.08] px-3 py-1 text-xs text-foreground/80">
      <span className="h-1.5 w-1.5 rounded-full bg-brass" />
      Curated specimen — precomputed real comparison{detail}
    </span>
  );
}
