"use client";

import { useEffect, useRef, useState } from "react";

interface Band {
  x_frac: number;
  w_frac: number;
}

function extent(...arrs: number[][]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const arr of arrs) {
    for (const v of arr) {
      if (!Number.isFinite(v)) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  return [lo, hi];
}

/**
 * Signature A and signature B overlaid at their best alignment, with the matched
 * striae bands highlighted. B is shifted onto A's frame using the offset implied by
 * the matched bands (correct by construction). On scroll-in it assembles: A draws,
 * then B, then the matched bands light up.
 */
export function AlignedSignatures({
  a,
  b,
  lag,
  bandsA,
  bandsB,
  className,
}: {
  a: number[];
  b: number[];
  lag: number;
  bandsA: Band[];
  bandsB: Band[];
  className?: string;
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
  const H = 190;
  const [lo, hi] = extent(a, b);
  const span = hi - lo || 1;
  const yv = (v: number) => H - 12 - ((v - lo) / span) * (H - 24);

  let shift = -lag / a.length;
  const m = Math.min(bandsA.length, bandsB.length);
  if (m > 0) {
    let s = 0;
    for (let i = 0; i < m; i++) s += bandsA[i].x_frac - bandsB[i].x_frac;
    shift = s / m;
  }

  const pathA = "M " + a.map((v, i) => `${((i / (a.length - 1)) * W).toFixed(1)},${yv(v).toFixed(1)}`).join(" L ");
  const pathB =
    "M " + b.map((v, k) => `${((k / (b.length - 1) + shift) * W).toFixed(1)},${yv(v).toFixed(1)}`).join(" L ");

  const draw = (delay: number) => ({
    strokeDasharray: 1,
    strokeDashoffset: shown ? 0 : 1,
    transition: `stroke-dashoffset 1.1s cubic-bezier(0.4, 0, 0.2, 1) ${delay}s`,
  });

  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={className} style={{ width: "100%" }}>
      {bandsA.map((r, i) => (
        <rect
          key={i}
          x={r.x_frac * W}
          y={0}
          width={r.w_frac * W}
          height={H}
          fill="#10b981"
          style={{ opacity: shown ? 0.16 : 0, transition: "opacity 0.6s ease 0.7s" }}
        />
      ))}
      <path d={pathB} fill="none" stroke="var(--accent-2)" strokeWidth={1.4} vectorEffect="non-scaling-stroke" opacity={0.8} pathLength={1} style={draw(0.35)} />
      <path d={pathA} fill="none" stroke="var(--accent)" strokeWidth={1.6} vectorEffect="non-scaling-stroke" pathLength={1} style={draw(0)} />
    </svg>
  );
}
