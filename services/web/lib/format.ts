// Shared likelihood-ratio formatting — human-readable, no scientific notation.
// "146", "1,500", "7.1", or "1 / 100". Used by the report view, the method
// walkthrough, and the homepage proof so they all read identically.

function human(x: number): string {
  if (x >= 100) return Math.round(x).toLocaleString("en-US");
  const s = x.toFixed(1);
  return s.endsWith(".0") ? s.slice(0, -2) : s;
}

/** "146" for LR ≥ 1, or "1 / 100" for LR < 1 (the "×" is added by the caller). */
export function formatLR(lr: number): string {
  return lr >= 1 ? human(lr) : `1 / ${human(1 / lr)}`;
}

/** Same as {@link formatLR} but with a "×" suffix on values ≥ 1: "146×" or "1 / 100". */
export function formatLRx(lr: number): string {
  return lr >= 1 ? `${human(lr)}×` : `1 / ${human(1 / lr)}`;
}
