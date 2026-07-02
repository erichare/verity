"use client";

import { useState } from "react";
import type { Vote } from "@/lib/studio";

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);
const clamp01 = (t: number) => Math.min(1, Math.max(0, t));

// Registration strength → a 0–1 factor driving dot opacity. Weak cells (low correlation) fade,
// so the prominent dots — including any hollow ones near the cluster — are the ones that matched
// strongly (and therefore dissent on twist, not for lack of a match). corr ~0.15→0, ~0.85→1.
const corrFactor = (c: number | undefined) => (c == null ? 0.85 : clamp01((c - 0.15) / 0.7));

// Plot area inside the 0–100 viewBox, leaving margins for the axes and their labels.
const L = 14;
const R = 95;
const T = 9;
const B = 84;
const px = (x: number) => L + clamp01(x) * (R - L);
const py = (y: number) => B - clamp01(y) * (B - T); // y = 1 → top

/**
 * The congruent-matching-regions moment, drawn from the engine's REAL per-window votes. Each
 * mark is tiled into windows (cells, for impressed); each window registers against the other
 * mark and proposes an alignment — a shift (and, for impressed, a twist). Every dot is one
 * window at the alignment it proposed: windows that agree land together in the centre
 * (filled brass = the consensus cluster), dissenters scatter to the edges (hollow). A
 * same-source pair forms a dense cluster; a different-source pair barely any. Hover a dot for
 * its real registration values. `progress` (0→1) reveals the dots, then the consensus.
 *
 * Synthetic fallback (live uploads, no per-window votes): `schematic` marks the plot as an
 * illustration — a SCHEMATIC badge on the plot, no strength/hover legend (the dots carry no
 * real values), and an explicit disclosure that the count and score derive from the report.
 */
export function CmrConsensus({
  votes,
  progress,
  nConsensus,
  axisX,
  axisY,
  schematic,
  className,
}: {
  votes: Vote[];
  progress: number;
  nConsensus: number;
  axisX: string;
  axisY: string;
  schematic?: boolean;
  className?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);

  const dotsIn = easeOut(clamp01(progress / 0.4));
  const focus = easeOut(clamp01((progress - 0.4) / 0.6));
  const total = votes.length;
  const liveAgree = Math.round(nConsensus * (0.3 + 0.7 * focus));

  // The consensus cluster's centre + extent (in plot coords), to draw the ring around it.
  const cons = votes.filter((v) => v.consensus);
  const cx = cons.length ? cons.reduce((s, v) => s + px(v.x), 0) / cons.length : 64;
  const cy = cons.length ? cons.reduce((s, v) => s + py(v.y), 0) / cons.length : 46;
  const spread = cons.length
    ? Math.max(...cons.map((v) => Math.hypot(px(v.x) - cx, py(v.y) - cy)))
    : 0;
  const ringR = Math.min(30, Math.max(7, spread + 4)) * focus;
  const showRing = cons.length >= 3;
  // Label above the ring, or below it when the cluster hugs the top edge (high-correlation
  // consensus sits near the top), clamped inside the plot.
  const labelAbove = cy - ringR - 2.5 > T + 1.5;
  const labelY = Math.min(B - 1, Math.max(T + 3, labelAbove ? cy - ringR - 2.5 : cy + ringR + 4.5));

  return (
    <div className={`relative flex flex-col ${className ?? ""}`}>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
          Comparison windows
        </span>
        <span className="font-mono text-[11px] tabular-nums">
          <span className="text-brass">{liveAgree}</span>
          {/* Schematic: the denominator would be the fabricated dot budget — don't show it. */}
          <span className="text-muted">{schematic ? " agree (derived)" : ` / ${total} agree`}</span>
        </span>
      </div>

      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" className="min-h-0 w-full flex-1">
        {schematic && (
          <g className="font-mono">
            <rect
              x={R - 24}
              y={T - 6}
              width={25}
              height={5.4}
              rx={1.2}
              fill="var(--background)"
              stroke="var(--muted)"
              strokeWidth={0.35}
              opacity={0.9}
            />
            <text
              x={R - 11.5}
              y={T - 2.2}
              textAnchor="middle"
              fontSize={2.9}
              fill="var(--muted)"
              style={{ letterSpacing: "0.18em" }}
            >
              SCHEMATIC
            </text>
          </g>
        )}
        {/* Axes name the plane: each dot is placed by the alignment its window proposes. No tick
            numbers — the real registration values live in the hover tooltip. */}
        <g opacity={0.55} className="font-mono">
          <line x1={L - 2} y1={B} x2={R + 1} y2={B} stroke="var(--muted)" strokeWidth={0.3} />
          <path d={`M${R + 1} ${B} l-2.2 -1.1 v2.2 z`} fill="var(--muted)" />
          <text x={(L + R) / 2} y={B + 7} textAnchor="middle" fontSize={2.9} fill="var(--muted)">
            {axisX} →
          </text>
          <line x1={L - 2} y1={B} x2={L - 2} y2={T - 1} stroke="var(--muted)" strokeWidth={0.3} />
          <path d={`M${L - 2} ${T - 1} l-1.1 2.2 h2.2 z`} fill="var(--muted)" />
          <text
            x={4}
            y={(T + B) / 2}
            textAnchor="middle"
            fontSize={2.9}
            fill="var(--muted)"
            transform={`rotate(-90 4 ${(T + B) / 2})`}
          >
            {axisY} →
          </text>
        </g>

        {showRing && (
          <circle cx={cx} cy={cy} r={ringR} fill="none" stroke="var(--brass)" strokeWidth={0.5} opacity={focus * 0.7} />
        )}
        {showRing && focus > 0.55 && (
          <text
            x={cx}
            y={labelY}
            textAnchor="middle"
            fontSize={3.4}
            fill="var(--brass)"
            opacity={(focus - 0.55) / 0.45}
            style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}
          >
            consensus
          </text>
        )}

        {votes.map((v, i) => {
          const x = px(v.x);
          const y = py(v.y);
          const hovered = hover === i;
          const interactive = !!v.tip;
          const cf = corrFactor(v.corr); // dot opacity ∝ registration strength
          const common = {
            onMouseEnter: interactive ? () => setHover(i) : undefined,
            onMouseLeave: interactive ? () => setHover(null) : undefined,
            style: interactive ? { cursor: "pointer" as const } : undefined,
          };
          if (v.consensus) {
            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                r={(hovered ? 2.1 : 1.5) * dotsIn}
                fill="var(--brass)"
                opacity={hovered ? 1 : dotsIn * (0.45 + 0.55 * cf)}
                {...common}
              />
            );
          }
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={(hovered ? 1.9 : 1.3) * dotsIn}
              fill={hovered ? "var(--muted)" : "none"}
              stroke="var(--muted)"
              strokeWidth={0.4}
              opacity={hovered ? 0.95 : dotsIn * (0.2 + 0.5 * cf)}
              {...common}
            />
          );
        })}

        {hover != null && votes[hover]?.tip && (
          <Tooltip x={px(votes[hover].x)} y={py(votes[hover].y)} tip={votes[hover].tip!} />
        )}
      </svg>

      <div className="mt-1.5 flex flex-col items-center gap-0.5 font-mono text-[10px] text-muted">
        <div className="flex items-center justify-center gap-4">
          <span className="inline-flex items-center gap-1.5">
            <svg width="9" height="9" viewBox="0 0 9 9" aria-hidden>
              <circle cx="4.5" cy="4.5" r="3" fill="var(--brass)" />
            </svg>
            agrees on alignment
          </span>
          <span className="inline-flex items-center gap-1.5">
            <svg width="9" height="9" viewBox="0 0 9 9" aria-hidden>
              <circle cx="4.5" cy="4.5" r="2.6" fill="none" stroke="var(--muted)" strokeWidth="0.9" />
            </svg>
            dissents
          </span>
        </div>
        {schematic ? (
          <span className="max-w-md text-center text-muted/70">
            Schematic illustration — the API does not expose per-window votes for uploads; the
            consensus count and score are derived from the real report.
          </span>
        ) : (
          <span className="text-muted/70">brighter = stronger match · hover for values</span>
        )}
      </div>
    </div>
  );
}

// An in-SVG hover card showing one window's real registration values (so it scales with the
// plot and never escapes the card). Flips to whichever side keeps it on-canvas.
function Tooltip({ x, y, tip }: { x: number; y: number; tip: Record<string, string> }) {
  const rows = Object.entries(tip);
  const lh = 3.6;
  const padX = 2.2;
  const padY = 2.4;
  const charW = 1.55;
  const w = padX * 2 + Math.max(...rows.map(([k, val]) => (k.length + val.length + 2) * charW));
  const h = padY * 2 + rows.length * lh;
  const left = x > 52;
  const bx = Math.min(99 - w, Math.max(1, left ? x - 3 - w : x + 3));
  const by = Math.min(99 - h, Math.max(1, y - h / 2));
  return (
    <g pointerEvents="none">
      <rect
        x={bx}
        y={by}
        width={w}
        height={h}
        rx={1.4}
        fill="var(--background)"
        stroke="var(--border)"
        strokeWidth={0.3}
        opacity={0.97}
      />
      {rows.map(([k, val], i) => (
        <text key={k} x={bx + padX} y={by + padY + (i + 0.8) * lh} fontSize={2.5} className="font-mono">
          <tspan fill="var(--muted)">{k}</tspan>
          <tspan fill="var(--foreground)" dx={1.2} style={{ fontWeight: 600 }}>
            {val}
          </tspan>
        </text>
      ))}
    </g>
  );
}
