"use client";

import { useMemo } from "react";

function minmax(arr: number[]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of arr) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return [lo, hi];
}

function kde(samples: number[], xs: number[], bw: number): number[] {
  const norm = 1 / (bw * Math.sqrt(2 * Math.PI) * samples.length);
  return xs.map((x) => {
    let s = 0;
    for (const v of samples) {
      const d = (x - v) / bw;
      s += Math.exp(-0.5 * d * d);
    }
    return norm * s;
  });
}

/** KM vs KNM reference score densities, with the comparison's score marked — showing
 *  which population it falls in (and therefore which way, and how strongly, the LR points). */
export function CalibrationChart({
  km,
  knm,
  score,
  lrLabel,
  className,
}: {
  km: number[];
  knm: number[];
  score: number;
  lrLabel: string;
  className?: string;
}) {
  const v = useMemo(() => {
    const [allLo, allHi] = minmax([...km, ...knm, score]);
    const pad = (allHi - allLo) * 0.06 || 1;
    const lo = allLo - pad;
    const hi = allHi + pad;
    const N = 160;
    const xs = Array.from({ length: N }, (_, i) => lo + ((hi - lo) * i) / (N - 1));
    const bw = (hi - lo) / 22;
    const kmY = kde(km, xs, bw);
    const knmY = kde(knm, xs, bw);
    const ymax = Math.max(...kmY, ...knmY) || 1;
    const xpos = (s: number) => (s - lo) / (hi - lo);
    return { xs, kmY, knmY, ymax, scoreX: xpos(score) };
  }, [km, knm, score]);

  const W = 1000;
  const H = 210;
  const base = H - 26;
  const yv = (d: number) => base - (d / v.ymax) * (base - 16);
  const area = (ys: number[]) => {
    const pts = ys.map((d, i) => `${((i / (ys.length - 1)) * W).toFixed(1)},${yv(d).toFixed(1)}`);
    return `M 0,${base} L ` + pts.join(" L ") + ` L ${W},${base} Z`;
  };
  const sx = v.scoreX * W;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={className} style={{ width: "100%" }}>
      <line x1="0" y1={base} x2={W} y2={base} stroke="var(--border)" strokeWidth={1} />
      <path d={area(v.knmY)} fill="#f43f5e" fillOpacity={0.18} stroke="#f43f5e" strokeOpacity={0.5} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      <path d={area(v.kmY)} fill="var(--accent)" fillOpacity={0.2} stroke="var(--accent)" strokeOpacity={0.7} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
      {/* the comparison's score */}
      <line x1={sx} y1={6} x2={sx} y2={base} stroke="var(--foreground)" strokeWidth={1.5} strokeDasharray="4 3" />
      <circle cx={sx} cy={6} r={4} fill="var(--foreground)" />
      <text x={Math.min(Math.max(sx, 60), W - 60)} y={20} textAnchor="middle" fontSize="13" fill="var(--foreground)">
        score {score.toFixed(3)} → LR {lrLabel}
      </text>
      <text x={12} y={base + 18} fontSize="12" fill="#f43f5e">different-source</text>
      <text x={W - 12} y={base + 18} textAnchor="end" fontSize="12" fill="var(--accent)">same-source</text>
    </svg>
  );
}
