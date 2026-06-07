"use client";

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
 * the matched bands (correct by construction), so where the marks agree the two
 * traces ride on top of each other.
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
  if (!a?.length || !b?.length) return null;
  const W = 1000;
  const H = 190;
  const [lo, hi] = extent(a, b);
  const span = hi - lo || 1;
  const yv = (v: number) => H - 12 - ((v - lo) / span) * (H - 24);

  // Shift (in [0,1] signature fraction) to overlay B onto A's frame.
  let shift = -lag / a.length;
  const m = Math.min(bandsA.length, bandsB.length);
  if (m > 0) {
    let s = 0;
    for (let i = 0; i < m; i++) s += bandsA[i].x_frac - bandsB[i].x_frac;
    shift = s / m;
  }

  const pathA =
    "M " + a.map((v, i) => `${((i / (a.length - 1)) * W).toFixed(1)},${yv(v).toFixed(1)}`).join(" L ");
  const pathB =
    "M " +
    b
      .map((v, k) => `${((k / (b.length - 1) + shift) * W).toFixed(1)},${yv(v).toFixed(1)}`)
      .join(" L ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={className} style={{ width: "100%" }}>
      {bandsA.map((r, i) => (
        <rect key={i} x={r.x_frac * W} y={0} width={r.w_frac * W} height={H} fill="#10b981" opacity={0.16} />
      ))}
      <path d={pathB} fill="none" stroke="var(--accent-2)" strokeWidth={1.4} vectorEffect="non-scaling-stroke" opacity={0.8} />
      <path d={pathA} fill="none" stroke="var(--accent)" strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
