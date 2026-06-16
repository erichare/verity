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

function Beat({ show, children }: { show: boolean; children: ReactNode }) {
  return (
    <div
      className={`transition-all duration-700 ease-out ${
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
  const step = useReveal(isRefusal(report) ? null : revealKey, 4);

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

  return (
    <div className="space-y-5">
      <Header aLabel={aLabel} bLabel={bLabel} result={result} />

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
            <p className="text-sm font-medium text-foreground">Aligned signatures</p>
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
            <p className="text-sm font-medium text-foreground">Where the score falls</p>
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

      <Beat show={step >= 4}>
        <ReportView report={report} animateIn showAttribution={false} />
      </Beat>
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
