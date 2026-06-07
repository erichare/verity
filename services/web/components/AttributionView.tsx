"use client";

import dynamic from "next/dynamic";
import type { AttributionRegion } from "@/lib/types";

const SurfaceViewer = dynamic(() => import("@/components/three/SurfaceViewer"), {
  ssr: false,
});

const VIEWER_CLASS =
  "h-60 w-full overflow-hidden rounded-xl border border-border bg-foreground/[0.02]";

export default function AttributionView({
  previews,
  regions,
  regionsB,
  domain,
}: {
  previews: { a: number[][]; b: number[][] };
  regions: AttributionRegion[];
  regionsB?: AttributionRegion[];
  domain?: string;
}) {
  const striated = domain === "striated";
  const n = regions.length;

  const heading = striated
    ? `Attribution — ${n} consecutive matching stria${n === 1 ? "" : "e"}`
    : `Attribution — ${n} congruent matching region${n === 1 ? "" : "s"}`;

  const blurb = striated
    ? "The glowing bands mark consecutive matching striae on the best-matching land of each bullet — windows that locked onto the same shift (the consecutive-matching-striae evidence). Drag to rotate the rendered surfaces."
    : "The glowing cells on Mark A independently agreed on a common registration with Mark B — the regions that drove the match (the CMC evidence). Drag to rotate the rendered surfaces.";

  const labelA = striated ? "Mark A — best-matching land" : "Mark A — congruent regions";
  const labelB = striated ? "Mark B — best-matching land" : "Mark B";

  return (
    <div className="space-y-3 border-t border-border pt-5">
      <p className="text-sm font-medium text-foreground">{heading}</p>
      <p className="text-xs text-muted">{blurb}</p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col items-center gap-1.5">
          <SurfaceViewer grid={previews.a} regions={regions} className={VIEWER_CLASS} />
          <span className="text-xs text-muted">{labelA}</span>
        </div>
        <div className="flex flex-col items-center gap-1.5">
          <SurfaceViewer grid={previews.b} regions={regionsB} className={VIEWER_CLASS} />
          <span className="text-xs text-muted">{labelB}</span>
        </div>
      </div>
    </div>
  );
}
