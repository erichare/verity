"use client";

import { useEffect, useState } from "react";
import { formatLR } from "@/lib/format";

/**
 * The likelihood ratio, optionally counting up (in log space, so it sweeps orders
 * of magnitude smoothly) on first reveal. Falls back to the final value instantly
 * when not animating or under prefers-reduced-motion.
 */
export function LRCounter({
  value,
  animate,
  className,
}: {
  value: number;
  animate?: boolean;
  className?: string;
}) {
  const [shown, setShown] = useState(value);

  useEffect(() => {
    if (!animate || !Number.isFinite(value) || value <= 0) {
      setShown(value);
      return;
    }
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setShown(value);
      return;
    }
    const logTarget = Math.log10(value); // 0 (LR=1) → target; works for exclusion too
    const start = performance.now();
    const dur = 900;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(Math.pow(10, logTarget * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    setShown(1);
    raf = requestAnimationFrame(tick);
    // Guarantee the final value lands even if rAF is throttled (background tab, headless).
    const done = window.setTimeout(() => setShown(value), dur + 80);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(done);
    };
  }, [value, animate]);

  return <span className={className}>{formatLR(shown)}</span>;
}
