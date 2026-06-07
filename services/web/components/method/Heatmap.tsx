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

export function Heatmap({ grid, className }: { grid: number[][]; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || !grid?.length) return;
    const rows = grid.length;
    const cols = grid[0].length;
    canvas.width = cols;
    canvas.height = rows;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const img = ctx.createImageData(cols, rows);
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const [r, g, b] = ramp(grid[y][x] ?? 0);
        const i = (y * cols + x) * 4;
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
    />
  );
}
