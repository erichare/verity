"use client";

import { useEffect, useRef } from "react";

// viridis control points — a perceptual, theme-neutral scientific colormap.
const VIRIDIS: [number, number, number][] = [
  [68, 1, 84],
  [59, 82, 139],
  [33, 145, 140],
  [94, 201, 98],
  [253, 231, 37],
];

function ramp(t: number): [number, number, number] {
  const c = Math.max(0, Math.min(1, t)) * (VIRIDIS.length - 1);
  const i = Math.floor(c);
  const f = c - i;
  const a = VIRIDIS[i];
  const b = VIRIDIS[Math.min(i + 1, VIRIDIS.length - 1)];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

// Areal maps are coarse grids (a breech-face scan is ~56×56). Drawing them at native size and
// letting CSS stretch the canvas ~10× makes the browser bilinear-blur a 56-px thumbnail — soft
// and muddy. Instead we resample the height field into a high-resolution backing buffer here,
// with our own bilinear interpolation, so the displayed map is a smooth *and* crisp surface
// (the buffer is ~1:1 with the on-screen size, so the browser barely rescales it).
const TARGET = 480; // backing-buffer long side, in px

export function Heatmap({
  grid,
  className,
  label,
}: {
  grid: number[][];
  className?: string;
  /** Text alternative for the rendered canvas (role="img"). */
  label?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !grid?.length) return;
    const rows = grid.length;
    const cols = grid[0].length;
    // Upsample by an integer factor so neither axis is below ~TARGET px (never downsample).
    const scale = Math.max(1, Math.round(TARGET / Math.max(rows, cols)));
    const w = cols * scale;
    const h = rows * scale;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = ctx.createImageData(w, h);
    const sx = cols > 1 ? (cols - 1) / (w - 1) : 0;
    const sy = rows > 1 ? (rows - 1) / (h - 1) : 0;
    for (let oy = 0; oy < h; oy++) {
      const gy = oy * sy;
      const y0 = Math.floor(gy);
      const y1 = Math.min(y0 + 1, rows - 1);
      const fy = gy - y0;
      for (let ox = 0; ox < w; ox++) {
        const gx = ox * sx;
        const x0 = Math.floor(gx);
        const x1 = Math.min(x0 + 1, cols - 1);
        const fx = gx - x0;
        // Bilinear blend of the four surrounding samples.
        const v00 = grid[y0][x0] ?? 0;
        const v01 = grid[y0][x1] ?? 0;
        const v10 = grid[y1][x0] ?? 0;
        const v11 = grid[y1][x1] ?? 0;
        const top = v00 + (v01 - v00) * fx;
        const bot = v10 + (v11 - v10) * fx;
        const [r, g, b] = ramp(top + (bot - top) * fy);
        const i = (oy * w + ox) * 4;
        img.data[i] = r;
        img.data[i + 1] = g;
        img.data[i + 2] = b;
        img.data[i + 3] = 255;
      }
    }
    ctx.putImageData(img, 0, 0);
  }, [grid]);

  return (
    <canvas
      ref={ref}
      className={className}
      style={{ width: "100%", height: "100%", display: "block" }}
      role="img"
      aria-label={label ?? "Heatmap of the scanned surface's height field"}
    />
  );
}
