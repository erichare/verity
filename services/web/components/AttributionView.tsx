"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import type { AttributionRegion } from "@/lib/types";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

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
  const reducedMotion = usePrefersReducedMotion();
  // null = follow the user's reduced-motion preference; the toggle overrides it.
  const [animateOverride, setAnimateOverride] = useState<boolean | null>(null);
  const animate = animateOverride ?? !reducedMotion;

  const heading = striated
    ? `Attribution — ${n} consecutive matching stria${n === 1 ? "" : "e"}`
    : `Attribution — ${n} congruent matching region${n === 1 ? "" : "s"}`;

  const blurb = striated
    ? "The glowing bands mark consecutive matching striae on the best-matching land of each bullet — windows that locked onto the same shift (the consecutive-matching-striae evidence). Use the rotation control or drag to inspect the rendered surfaces."
    : "The glowing cells agreed on a common registration — the same congruent regions are highlighted on both marks, at their matched positions (the CMC evidence). Use the rotation control or drag to inspect the rendered surfaces.";

  const labelA = striated ? "Mark A — best-matching land" : "Mark A — congruent regions";
  const labelB = striated ? "Mark B — best-matching land" : "Mark B — congruent regions";

  return (
    <div className="space-y-3 border-t border-border pt-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-foreground">{heading}</h3>
        <button
          type="button"
          onClick={() => setAnimateOverride(!animate)}
          aria-pressed={animate}
          title={animate ? "Pause the rotating 3-D view" : "Rotate the 3-D view"}
          className={`flex min-h-10 items-center rounded-full border px-3 py-2 text-xs font-medium transition ${
            animate
              ? "border-brass/40 bg-brass/15 text-brass-text"
              : "border-border text-muted hover:text-foreground"
          }`}
        >
          {animate ? "Pause rotation" : "Rotate view"}
        </button>
      </div>
      <p className="text-xs text-muted">{blurb}</p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="flex flex-col items-center gap-1.5">
          <div className={VIEWER_CLASS}>
            <SurfaceViewer
              grid={previews.a}
              regions={regions}
              autoRotate={animate}
              label={`3-D rendering of ${labelA.toLowerCase()}; use the nearby rotation control or drag to inspect`}
              className="h-full w-full"
            />
          </div>
          <span className="text-xs text-muted">{labelA}</span>
        </div>
        <div className="flex flex-col items-center gap-1.5">
          <div className={VIEWER_CLASS}>
            <SurfaceViewer
              grid={previews.b}
              regions={regionsB}
              autoRotate={animate}
              label={`3-D rendering of ${labelB.toLowerCase()}; use the nearby rotation control or drag to inspect`}
              className="h-full w-full"
            />
          </div>
          <span className="text-xs text-muted">{labelB}</span>
        </div>
      </div>
    </div>
  );
}
