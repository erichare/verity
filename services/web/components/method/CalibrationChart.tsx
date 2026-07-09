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

function DensityChart({
  kmY,
  knmY,
  ymax,
  scoreX,
  score,
  lrLabel,
  width,
  mobile = false,
  className,
}: {
  kmY: number[];
  knmY: number[];
  ymax: number;
  scoreX: number;
  score: number;
  lrLabel: string;
  width: number;
  mobile?: boolean;
  className: string;
}) {
  const H = 210;
  const base = H - 26;
  const yv = (d: number) => base - (d / ymax) * (base - 16);
  const area = (ys: number[]) => {
    const pts = ys.map((d, i) => `${((i / (ys.length - 1)) * width).toFixed(1)},${yv(d).toFixed(1)}`);
    return `M 0,${base} L ` + pts.join(" L ") + ` L ${width},${base} Z`;
  };
  const sx = scoreX * width;
  const scoreInset = mobile ? 120 : 60;
  const scoreLabelSize = mobile ? 17 : 13;
  const populationLabelSize = mobile ? 16 : 12;
  const edgeInset = mobile ? 8 : 12;

  return (
    <svg
      viewBox={`0 0 ${width} ${H}`}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <line x1="0" y1={base} x2={width} y2={base} stroke="var(--border)" strokeWidth={1} />
      <path
        d={area(knmY)}
        fill="var(--oxblood)"
        fillOpacity={0.18}
        stroke="var(--oxblood)"
        strokeOpacity={0.5}
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
      <path
        d={area(kmY)}
        fill="var(--accent)"
        fillOpacity={0.2}
        stroke="var(--accent)"
        strokeOpacity={0.7}
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
      <line
        x1={sx}
        y1={6}
        x2={sx}
        y2={base}
        stroke="var(--foreground)"
        strokeWidth={1.5}
        strokeDasharray="4 3"
      />
      <circle cx={sx} cy={6} r={4} fill="var(--foreground)" />
      <text
        x={Math.min(Math.max(sx, scoreInset), width - scoreInset)}
        y={mobile ? 22 : 20}
        textAnchor="middle"
        fontSize={scoreLabelSize}
        fill="var(--foreground)"
      >
        score {score.toFixed(3)} → LR {lrLabel}
      </text>
      <text x={edgeInset} y={base + 18} fontSize={populationLabelSize} fill="var(--oxblood)">
        different-source
      </text>
      <text
        x={width - edgeInset}
        y={base + 18}
        textAnchor="end"
        fontSize={populationLabelSize}
        fill="var(--accent)"
      >
        same-source
      </text>
    </svg>
  );
}

/** KM vs KNM reference score densities, with the comparison's score marked — showing
 *  which population it falls in (and therefore which way, and how strongly, the LR points). */
export function CalibrationChart({
  km,
  knm,
  score,
  lrLabel,
  className,
  label,
}: {
  km: number[];
  knm: number[];
  score: number;
  lrLabel: string;
  className?: string;
  /** Text alternative for the chart (role="img"). */
  label?: string;
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

  const svgSizeClass = className ? "h-full w-full" : "h-auto w-full";
  const accessibleLabel =
    label ??
    `Chart: score densities of ${km.length} same-source and ${knm.length} different-source reference pairs, with this comparison's score ${score.toFixed(3)} marked — mapping to a likelihood ratio of ${lrLabel}`;

  return (
    <div
      className={className}
      role="img"
      aria-label={accessibleLabel}
    >
      <DensityChart
        kmY={v.kmY}
        knmY={v.knmY}
        ymax={v.ymax}
        scoreX={v.scoreX}
        score={score}
        lrLabel={lrLabel}
        width={360}
        mobile
        className={`${svgSizeClass} block sm:hidden`}
      />
      <DensityChart
        kmY={v.kmY}
        knmY={v.knmY}
        ymax={v.ymax}
        scoreX={v.scoreX}
        score={score}
        lrLabel={lrLabel}
        width={1000}
        className={`${svgSizeClass} hidden sm:block`}
      />
    </div>
  );
}
