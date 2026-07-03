"use client";

import { useEffect, useRef, useState } from "react";

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

/** A single 1-D striation signature drawn as an elegant line with a soft area fill,
 *  drawing itself on when scrolled into view. */
export function SignaturePlot({
  values,
  className,
  label,
}: {
  values: number[];
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
    <svg
      ref={ref}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={className}
      style={{ width: "100%" }}
      role="img"
      aria-label={
        label ??
        `Chart: a 1-D striation signature of ${values.length} samples — the height profile the pipeline extracts from the scan and compares`
      }
    >
      <defs>
        <linearGradient id="sig-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#sig-fill)" style={{ opacity: shown ? 1 : 0, transition: "opacity 0.8s ease 0.3s" }} />
      <path
        d={line}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={2}
        vectorEffect="non-scaling-stroke"
        pathLength={1}
        style={{
          strokeDasharray: 1,
          strokeDashoffset: shown ? 0 : 1,
          transition: "stroke-dashoffset 1.3s cubic-bezier(0.4, 0, 0.2, 1)",
        }}
      />
    </svg>
  );
}
