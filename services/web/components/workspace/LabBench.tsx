"use client";

import type { ReactNode } from "react";
import { isRefusal, type BenchResult } from "@/lib/types";
import ReportView from "@/components/ReportView";
import RefusalView from "@/components/RefusalView";
import AttributionView from "@/components/AttributionView";
import { AlignedSignatures } from "@/components/method/AlignedSignatures";
import { CalibrationChart } from "@/components/method/CalibrationChart";
import { ProvenanceBadge } from "./ProvenanceBadge";
import { useReveal } from "./useReveal";
import { formatLR } from "@/lib/format";
import { LinkArrow } from "@/components/LinkArrow";

function Beat({ show, children }: { show: boolean; children: ReactNode }) {
  return (
    <div
      aria-hidden={!show}
      inert={!show ? true : undefined}
      className={`transition-all duration-700 ease-out motion-reduce:transform-none motion-reduce:transition-none ${
        show ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-2 opacity-0"
      }`}
    >
      {children}
    </div>
  );
}

/**
 * The comparison "bench": once both specimens are chosen, a 4-beat reveal plays —
 * the matched surfaces/striae, then the aligned signatures, then where the score
 * falls on the reference population, then the verdict (LR counting up). Every beat
 * maps to a real precomputed artifact; the *order* is what makes it land. Reused for
 * live uploads too, skipping beats whose data is absent.
 */
export function LabBench({
  result,
  revealKey,
  aLabel,
  bLabel,
}: {
  result: BenchResult;
  revealKey: string;
  aLabel?: string;
  bLabel?: string;
}) {
  const report = result.report;
  const step = useReveal(isRefusal(report) ? null : revealKey, 3);

  if (isRefusal(report)) {
    return (
      <div className="space-y-4">
        <Header aLabel={aLabel} bLabel={bLabel} result={result} />
        <RefusalView result={report} />
      </div>
    );
  }

  const hasSurfaces = !!report.previews && report.attribution.length > 0;
  const hasSignatures = !!result.signatures;
  const hasCalibration = !!result.calibration;

  // Honest-calibration disclosure: when we know the ground-truth relation (gallery
  // pairs carry it) and the LR points the *other* way, say so plainly rather than
  // hiding it. A weak LR on a known different-source pair is calibration working, not
  // a bug — the whole promise is a weight of evidence, not a verdict.
  const lrDirection = report.log10_lr > 0 ? "same" : report.log10_lr < 0 ? "different" : "neutral";
  const groundTruthMismatch =
    (result.relation === "KNM" && lrDirection === "same") ||
    (result.relation === "KM" && lrDirection === "different");
  const resultId = `comparison-result-${revealKey.replace(/[^a-zA-Z0-9_-]/g, "-") || "current"}`;

  return (
    <div className="space-y-5">
      <Header aLabel={aLabel} bLabel={bLabel} result={result} />

      <a
        href={`#${resultId}`}
        className="glass flex items-center justify-between gap-4 rounded-xl p-4 transition hover:border-accent/50 sm:hidden"
      >
        <span>
          <span className="block text-[10px] font-medium uppercase tracking-[0.14em] text-muted">
            Calibrated result
          </span>
          <span
            className={`mt-1 block font-mono text-2xl font-semibold ${
              lrDirection === "same"
                ? "accent-text"
                : lrDirection === "different"
                  ? "text-oxblood"
                  : "text-foreground"
            }`}
          >
            {formatLR(report.likelihood_ratio)}
          </span>
          <span className="mt-1 block text-xs text-foreground/75">{report.verbal}</span>
        </span>
        <span className="shrink-0 text-xs font-medium text-foreground/70">
          Full result<LinkArrow className="ml-1" />
        </span>
      </a>

      {groundTruthMismatch && (
        <p className="rounded-lg border border-brass/30 bg-brass/[0.06] p-3 text-xs leading-relaxed text-foreground/80">
          This is a known{" "}
          <strong className="text-foreground">
            {result.relation === "KNM" ? "different-source" : "same-source"}
          </strong>{" "}
          pair, yet the likelihood ratio leans the other way — weakly. That is what honest
          calibration looks like: Verity reports the weight of evidence the surfaces actually
          carry, not the answer you already know. A weak, near-1 LR is the calibrated system
          declining to overclaim.
        </p>
      )}

      {hasSurfaces && (
        <Beat show={step >= 1}>
          <AttributionView
            previews={report.previews!}
            regions={report.attribution}
            regionsB={report.attribution_b}
            domain={report.domain}
          />
        </Beat>
      )}

      {hasSignatures && (
        <Beat show={step >= 2}>
          <div className="space-y-2 border-t border-border pt-5">
            <h3 className="text-sm font-medium text-foreground">Aligned signatures</h3>
            <p className="text-xs text-muted">
              The two profiles on one scale; matched striae are linked. Parallel links = a
              real, consistent correspondence.
            </p>
            <AlignedSignatures
              a={result.signatures!.a}
              b={result.signatures!.b}
              bandsA={result.signatures!.bandsA}
              bandsB={result.signatures!.bandsB}
            />
          </div>
        </Beat>
      )}

      {hasCalibration && (
        <Beat show={step >= 3}>
          <div className="space-y-2 border-t border-border pt-5">
            <h3 className="text-sm font-medium text-foreground">Where the score falls</h3>
            <p className="text-xs text-muted">
              The comparison&rsquo;s score against the reference population&rsquo;s
              same-source and different-source distributions — which way, and how strongly,
              the likelihood ratio points.
            </p>
            <CalibrationChart
              km={result.calibration!.km}
              knm={result.calibration!.knm}
              score={result.calibration!.score}
              lrLabel={result.calibration!.lrLabel}
            />
          </div>
        </Beat>
      )}

      <div id={resultId} className="scroll-mt-24">
        <ReportView key={resultId} report={report} animateIn showAttribution={false} />
      </div>
    </div>
  );
}

function Header({
  aLabel,
  bLabel,
  result,
}: {
  aLabel?: string;
  bLabel?: string;
  result: BenchResult;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      {(aLabel || bLabel) && (
        <p className="text-sm text-muted">
          <span className="font-medium text-foreground">{aLabel ?? "Mark A"}</span>
          <span className="mx-2 text-muted">vs</span>
          <span className="font-medium text-foreground">{bLabel ?? "Mark B"}</span>
        </p>
      )}
      <ProvenanceBadge result={result} />
    </div>
  );
}
