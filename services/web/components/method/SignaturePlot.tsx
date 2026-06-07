"use client";

function extent(values: number[]): [number, number] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (!Number.isFinite(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return [lo, hi];
}

/** A single 1-D striation signature drawn as an elegant line with a soft area fill. */
export function SignaturePlot({
  values,
  className,
}: {
  values: number[];
  className?: string;
}) {
  if (!values?.length) return null;
  const W = 1000;
  const H = 140;
  const [lo, hi] = extent(values);
  const span = hi - lo || 1;
  const y = (v: number) => H - 10 - ((v - lo) / span) * (H - 20);
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * W).toFixed(1)},${y(v).toFixed(1)}`);
  const line = "M " + pts.join(" L ");
  const area = `${line} L ${W},${H} L 0,${H} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={className} style={{ width: "100%" }}>
      <defs>
        <linearGradient id="sig-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#sig-fill)" />
      <path d={line} fill="none" stroke="var(--accent)" strokeWidth={2} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
