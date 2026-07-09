"use client";

import { useEffect, useRef, useState } from "react";
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
  const ref = useRef<HTMLSpanElement>(null);
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
    const el = ref.current;
    if (!el) return;
    // Keep offscreen and assistive-technology output accurate until the visual
    // count-up begins at the moment the result enters the viewport.
    setShown(value);

    let raf = 0;
    let done = 0;
    const run = () => {
      const logTarget = Math.log10(value); // 0 (LR=1) → target; works for exclusion too
      const start = performance.now();
      const dur = 900;
      const tick = (t: number) => {
        const p = Math.min(1, (t - start) / dur);
        const eased = 1 - Math.pow(1 - p, 3);
        setShown(Math.pow(10, logTarget * eased));
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      setShown(1);
      raf = requestAnimationFrame(tick);
      // Guarantee the final value lands even if rAF is throttled (background tab, headless).
      done = window.setTimeout(() => setShown(value), dur + 80);
    };

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          run();
          observer.disconnect();
        }
      },
      { threshold: 0.45 },
    );
    observer.observe(el);

    return () => {
      observer.disconnect();
      cancelAnimationFrame(raf);
      window.clearTimeout(done);
    };
  }, [value, animate]);

  return <span ref={ref} className={className}>{formatLR(shown)}</span>;
}
