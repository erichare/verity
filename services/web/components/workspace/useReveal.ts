"use client";

import { useEffect, useState } from "react";

/**
 * Advance a choreographed reveal: a `step` that climbs 0 → `steps` over time and
 * resets whenever `key` changes (a new comparison). Components gate their entrance
 * on `step >= n`. Honors prefers-reduced-motion by jumping straight to the end.
 */
export function useReveal(key: string | null, steps: number, intervalMs = 550): number {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!key) {
      setStep(0);
      return;
    }
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setStep(steps);
      return;
    }
    setStep(0);
    const timers = Array.from({ length: steps }, (_, i) =>
      window.setTimeout(() => setStep(i + 1), (i + 1) * intervalMs),
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [key, steps, intervalMs]);

  return step;
}
