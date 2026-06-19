"use client";

import dynamic from "next/dynamic";
import { AlignedSignatures } from "@/components/method/AlignedSignatures";
import { CalibrationChart } from "@/components/method/CalibrationChart";
import { Heatmap } from "@/components/method/Heatmap";
import ReportView from "@/components/ReportView";
import type { Stage, StudioRun } from "@/lib/studio";
import { CmrConsensus } from "./CmrConsensus";

// The WebGL surface is client-only and heavy; load it lazily so the shell paints first.
const SurfaceViewer = dynamic(() => import("@/components/three/SurfaceViewer"), { ssr: false });

function SurfacePane({
  label,
  grid,
  regions,
}: {
  label: string;
  grid: number[][];
  regions?: StudioRun["regionsA"];
}) {
  return (
    <div className="relative min-h-0 min-w-0 flex-1">
      <SurfaceViewer grid={grid} regions={regions} className="h-full w-full" />
      <span className="pointer-events-none absolute left-3 top-3 font-mono text-[10px] uppercase tracking-wider text-muted">
        {label}
      </span>
    </div>
  );
}

/**
 * The dominant stage: two surface scans rendered in 3-D persist across every step (so the
 * topography never leaves the screen), with each step's 2-D view — areal map, aligned
 * signatures, the CMR consensus scatter, calibration, verdict — cross-fading in front of a
 * receded scene. Continuity, not eight disconnected charts.
 */
export function StageStage({
  run,
  stage,
  progress,
}: {
  run: StudioRun;
  stage: Stage;
  progress: number;
}) {
  const showBand = stage.id === "preprocess";
  const showRegions = stage.display.type === "surfaces" && stage.display.variant === "attribution";
  const gridA = showBand ? run.bandA : run.gridA;
  const gridB = showBand ? run.bandB : run.gridB;

  return (
    <div className="relative h-full w-full overflow-hidden">
      {/* Persistent 3-D layer — recedes behind the 2-D overlays. */}
      <div
        className="absolute inset-0 flex gap-4 p-4 transition-all duration-700"
        style={{
          opacity: stage.recede ? 0.2 : 1,
          filter: stage.recede ? "blur(3px) saturate(0.8)" : "none",
          transform: stage.recede ? "scale(0.96)" : "scale(1)",
        }}
      >
        <SurfacePane label={run.aLabel} grid={gridA} regions={showRegions ? run.regionsA : undefined} />
        <SurfacePane label={run.bLabel} grid={gridB} regions={showRegions ? run.regionsB : undefined} />
      </div>

      {/* Per-stage 2-D overlay. */}
      <Overlay run={run} stage={stage} progress={progress} />
    </div>
  );
}

function Overlay({ run, stage, progress }: { run: StudioRun; stage: Stage; progress: number }) {
  const d = stage.display;

  if (d.type === "areal") {
    return (
      <Frame>
        <div className="stage-card aspect-square w-full max-w-[min(70vh,560px)] overflow-hidden rounded-2xl p-2">
          <Heatmap grid={d.grid} className="rounded-xl" />
        </div>
      </Frame>
    );
  }

  if (d.type === "signatures") {
    return (
      <Frame>
        <div className="stage-card w-full max-w-3xl rounded-2xl p-5">
          <AlignedSignatures a={d.a} b={d.b} bandsA={d.bandsA} bandsB={d.bandsB} />
        </div>
      </Frame>
    );
  }

  if (d.type === "cmr") {
    return (
      <Frame>
        <div className="stage-card aspect-square w-full max-w-[min(64vh,520px)] rounded-2xl p-4">
          <CmrConsensus
            votes={d.votes}
            progress={progress}
            nConsensus={d.nConsensus}
            relation={d.relation}
            className="h-full w-full"
          />
        </div>
      </Frame>
    );
  }

  if (d.type === "calibration") {
    return (
      <Frame>
        <div className="stage-card w-full max-w-3xl rounded-2xl p-5">
          <CalibrationChart km={d.km} knm={d.knm} score={d.score} lrLabel={d.lrLabel} />
        </div>
      </Frame>
    );
  }

  if (d.type === "verdict") {
    return (
      <div className="absolute inset-0 flex items-center justify-center overflow-y-auto p-4 sm:p-8">
        <div className="w-full max-w-2xl">
          <ReportView report={run.report} animateIn showAttribution={false} />
        </div>
      </div>
    );
  }

  return null; // surfaces stage — the 3-D layer is the content
}

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-4 sm:p-8">
      <div className="pointer-events-auto flex w-full items-center justify-center">{children}</div>
    </div>
  );
}
