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
}: {
  previews: { a: number[][]; b: number[][] };
  regions: AttributionRegion[];
}) {
  return (
    <div className="space-y-3 border-t border-border pt-5">
      <p className="text-sm font-medium text-foreground">
        Attribution — {regions.length} congruent matching region{regions.length === 1 ? "" : "s"}
      </p>
      <p className="text-xs text-muted">
        The glowing cells on Mark A independently agreed on a common registration with Mark B — the
        regions that drove the match (the consecutive-matching-striae analog). Drag to rotate; the
        examiner can see and verify exactly what the evidence rests on.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col items-center gap-1.5">
          <SurfaceViewer grid={previews.a} regions={regions} className={VIEWER_CLASS} />
          <span className="text-xs text-muted">Mark A — congruent regions</span>
        </div>
        <div className="flex flex-col items-center gap-1.5">
          <SurfaceViewer grid={previews.b} className={VIEWER_CLASS} />
          <span className="text-xs text-muted">Mark B</span>
        </div>
      </div>
    </div>
  );
}
