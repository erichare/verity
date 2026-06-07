"use client";

import { useEffect, useRef } from "react";
import type { AttributionRegion } from "@/lib/types";

const SIZE = 240;

function PreviewCanvas({
  grid,
  regions,
  label,
}: {
  grid: number[][];
  regions?: AttributionRegion[];
  label: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !grid?.length) return;
    const rows = grid.length;
    const cols = grid[0].length;
    canvas.width = SIZE;
    canvas.height = SIZE;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // grayscale at native resolution, then nearest-neighbour scale up
    const img = ctx.createImageData(cols, rows);
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const v = Math.round((grid[y][x] ?? 0) * 255);
        const i = (y * cols + x) * 4;
        img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
        img.data[i + 3] = 255;
      }
    }
    const tmp = document.createElement("canvas");
    tmp.width = cols;
    tmp.height = rows;
    tmp.getContext("2d")!.putImageData(img, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(tmp, 0, 0, SIZE, SIZE);

    if (regions?.length) {
      ctx.strokeStyle = "rgba(16,185,129,0.95)";
      ctx.lineWidth = 2;
      for (const r of regions) {
        ctx.strokeRect(r.x_frac * SIZE, r.y_frac * SIZE, r.w_frac * SIZE, r.h_frac * SIZE);
      }
    }
  }, [grid, regions]);

  return (
    <div className="flex flex-col items-center gap-1">
      <canvas ref={ref} className="rounded-lg border border-slate-200 bg-slate-900" />
      <span className="text-xs text-slate-400">{label}</span>
    </div>
  );
}

export default function AttributionView({
  previews,
  regions,
}: {
  previews: { a: number[][]; b: number[][] };
  regions: AttributionRegion[];
}) {
  return (
    <div className="space-y-3 border-t border-slate-100 pt-5">
      <p className="text-sm font-medium text-slate-700">
        Attribution — {regions.length} congruent matching region{regions.length === 1 ? "" : "s"}
      </p>
      <p className="text-xs text-slate-500">
        The highlighted cells on Mark A independently agreed on a common registration with Mark B —
        the regions that drove the match (the consecutive-matching-striae analog). The examiner can
        see and verify exactly what the evidence rests on.
      </p>
      <div className="grid grid-cols-2 gap-4">
        <PreviewCanvas grid={previews.a} regions={regions} label="Mark A — congruent regions" />
        <PreviewCanvas grid={previews.b} label="Mark B" />
      </div>
    </div>
  );
}
