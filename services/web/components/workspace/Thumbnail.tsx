"use client";

import { useEffect, useRef } from "react";

/**
 * A cheap, static specimen preview — no Three.js. 2-D marks (bullets, cartridge
 * cases) render their grayscale height grid; toolmarks render their 1-D striation
 * profile as a sparkline in the brand accent. Used on every gallery card so the
 * picker stays light (only the two *selected* specimens get WebGL on the bench).
 */
export function Thumbnail({
  grid,
  signature,
  className,
  size = 120,
}: {
  grid?: number[][];
  signature?: number[];
  className?: string;
  size?: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = ref.current;
    const ctx = cv?.getContext("2d");
    if (!cv || !ctx) return;
    ctx.clearRect(0, 0, cv.width, cv.height);

    if (grid && grid.length && grid[0]?.length) {
      const h = grid.length;
      const w = grid[0].length;
      const img = ctx.createImageData(w, h);
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const v = Math.max(0, Math.min(1, grid[y][x] ?? 0));
          const g = Math.round(v * 255);
          const i = (y * w + x) * 4;
          img.data[i] = g;
          img.data[i + 1] = g;
          img.data[i + 2] = g;
          img.data[i + 3] = 255;
        }
      }
      const tmp = document.createElement("canvas");
      tmp.width = w;
      tmp.height = h;
      tmp.getContext("2d")?.putImageData(img, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(tmp, 0, 0, cv.width, cv.height);
      return;
    }

    if (signature && signature.length) {
      const accent =
        getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() || "#0e2a47";
      const n = signature.length;
      let lo = Infinity;
      let hi = -Infinity;
      for (const v of signature) {
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
      const pad = (hi - lo) * 0.12 || 1;
      lo -= pad;
      hi += pad;
      ctx.strokeStyle = accent;
      ctx.lineWidth = 1.5;
      ctx.lineJoin = "round";
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * cv.width;
        const y = cv.height - ((signature[i] - lo) / (hi - lo)) * cv.height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }, [grid, signature]);

  return <canvas ref={ref} width={size} height={size} className={className} aria-hidden />;
}
