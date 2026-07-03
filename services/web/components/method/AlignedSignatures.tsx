"use client";

import { useEffect, useRef, useState } from "react";

interface Band {
  x_frac: number;
  w_frac: number;
}

function extent(arr: number[]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of arr) {
    if (!Number.isFinite(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return [lo, hi];
}

/**
 * Signature A (top) and signature B (bottom) on a *shared pixel scale*, so their real
 * lengths show honestly. The matched striae are highlighted on each and linked by
 * connectors: near-vertical, parallel links = a real, consistent correspondence;
 * few or crossed links = no match. On scroll-in the traces draw, then the links light up.
 */
export function AlignedSignatures({
  a,
  b,
  bandsA,
  bandsB,
  className,
  label,
}: {
  a: number[];
  b: number[];
  bandsA: Band[];
  bandsB: Band[];
  className?: string;
  /** Text alternative for the chart (role="img"). */
  label?: string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setShown(true);
      return;
    }
    const io = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting) {
          setShown(true);
          io.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  if (!a?.length || !b?.length) return null;
  const W = 1000;
  const H = 210;
  const laneH = 74;
  const gap = 30;
  const aY0 = 10;
  const aY1 = aY0 + laneH;
  const bY0 = aY1 + gap;
  const bY1 = bY0 + laneH;
  const maxLen = Math.max(a.length, b.length);
  const xs = (px: number) => (px / maxLen) * W;

  const curve = (arr: number[], y0: number, y1: number) => {
    const [lo, hi] = extent(arr);
    const span = hi - lo || 1;
    const yv = (v: number) => y1 - 5 - ((v - lo) / span) * (y1 - y0 - 10);
    return "M " + arr.map((v, i) => `${xs(i).toFixed(1)},${yv(v).toFixed(1)}`).join(" L ");
  };

  const draw = (delay: number) => ({
    strokeDasharray: 1,
    strokeDashoffset: shown ? 0 : 1,
    transition: `stroke-dashoffset 1.1s cubic-bezier(0.4, 0, 0.2, 1) ${delay}s`,
  });
  const fade = (delay: number) => ({ opacity: shown ? 1 : 0, transition: `opacity 0.5s ease ${delay}s` });
  const m = Math.min(bandsA.length, bandsB.length);

  return (
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      className={className}
      style={{ width: "100%" }}
      role="img"
      aria-label={
        label ??
        `Chart: the 1-D striation signatures of mark A and mark B drawn on one shared scale, with ${m} matched region${m === 1 ? "" : "s"} highlighted and linked between the two traces`
      }
    >
      {bandsA.map((r, i) => (
        <rect key={`a${i}`} x={xs(r.x_frac * a.length)} y={aY0} width={xs(r.w_frac * a.length)} height={laneH} fill="var(--brass)" fillOpacity={0.16} style={fade(0.7)} />
      ))}
      {bandsB.map((r, i) => (
        <rect key={`b${i}`} x={xs(r.x_frac * b.length)} y={bY0} width={xs(r.w_frac * b.length)} height={laneH} fill="var(--brass)" fillOpacity={0.16} style={fade(0.7)} />
      ))}
      {Array.from({ length: m }).map((_, i) => (
        <line
          key={`c${i}`}
          x1={xs((bandsA[i].x_frac + bandsA[i].w_frac / 2) * a.length)}
          y1={aY1}
          x2={xs((bandsB[i].x_frac + bandsB[i].w_frac / 2) * b.length)}
          y2={bY0}
          stroke="var(--brass)"
          strokeWidth={1}
          opacity={0.55}
          style={fade(0.9)}
        />
      ))}
      <path d={curve(a, aY0, aY1)} fill="none" stroke="var(--accent)" strokeWidth={1.6} vectorEffect="non-scaling-stroke" pathLength={1} style={draw(0)} />
      <path d={curve(b, bY0, bY1)} fill="none" stroke="var(--accent-2)" strokeWidth={1.6} vectorEffect="non-scaling-stroke" pathLength={1} style={draw(0.35)} />
      <text x={6} y={aY0 + 12} fontSize="11" fill="var(--muted)">Mark A</text>
      <text x={6} y={bY0 + 12} fontSize="11" fill="var(--muted)">Mark B</text>
    </svg>
  );
}
