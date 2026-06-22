"use client";

import type { Vote } from "@/lib/studio";

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * The congruent-matching-regions moment: the two marks are tiled into many small windows, and
 * each window casts a vote on how to align them. As the stage plays, the windows that agree on
 * the same shift-and-twist (filled brass) migrate into a tight consensus cluster, while the
 * dissenters (hollow) stay scattered. A same-source pair locks into consensus; a
 * different-source pair never does. `progress` (0→1) drives the convergence.
 *
 * The header count, the labelled legend, and the "consensus" call-out exist so the graphic
 * reads on its own — each dot is one comparison window; filled = agrees, hollow = dissents.
 */
export function CmrConsensus({
  votes,
  progress,
  nConsensus,
  relation,
  className,
}: {
  votes: Vote[];
  progress: number;
  nConsensus: number;
  relation: "KM" | "KNM";
  className?: string;
}) {
  const e = easeOut(progress);
  const ring = nConsensus >= 6 && relation === "KM";
  const agreeing = votes.filter((v) => v.consensus).length;
  const total = votes.length;
  // The count ramps up as the agreeing windows migrate together.
  const liveAgree = Math.round(agreeing * e);

  return (
    <div className={`flex flex-col ${className ?? ""}`}>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
          Comparison windows
        </span>
        <span className="font-mono text-[11px] tabular-nums">
          <span className="text-brass">{liveAgree}</span>
          <span className="text-muted"> / {total} agree</span>
        </span>
      </div>

      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="xMidYMid meet"
        className="min-h-0 w-full flex-1"
      >
        {/* Axes name what the plane means: each window is placed by the alignment it proposes —
            how far to shift and how much to twist (rotate) to line its patch up. Windows that
            propose the same shift-and-twist land together. The layout is schematic (no measured
            units, hence no ticks); the message is the clustering, not the coordinates. */}
        <g opacity={0.55} className="font-mono">
          <line x1={7} y1={92} x2={93} y2={92} stroke="var(--muted)" strokeWidth={0.3} />
          <path d="M93 92 l-2.2 -1.1 v2.2 z" fill="var(--muted)" />
          <text x={50} y={98.5} textAnchor="middle" fontSize={3} fill="var(--muted)">
            shift →
          </text>
          <line x1={7} y1={92} x2={7} y2={9} stroke="var(--muted)" strokeWidth={0.3} />
          <path d="M7 9 l-1.1 2.2 h2.2 z" fill="var(--muted)" />
          <text
            x={2.8}
            y={50}
            textAnchor="middle"
            fontSize={3}
            fill="var(--muted)"
            transform="rotate(-90 2.8 50)"
          >
            twist →
          </text>
        </g>
        {ring && (
          <circle
            cx={64}
            cy={50}
            r={4 + e * 16}
            fill="none"
            stroke="var(--brass)"
            strokeWidth={0.5}
            opacity={e * 0.7}
          />
        )}
        {ring && e > 0.55 && (
          <text
            x={64}
            y={26}
            textAnchor="middle"
            fontSize={3.6}
            fill="var(--brass)"
            opacity={(e - 0.55) / 0.45}
            style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}
          >
            consensus
          </text>
        )}
        {votes.map((v, i) => {
          const x = v.hx + (v.tx - v.hx) * e;
          const y = v.hy + (v.ty - v.hy) * e;
          if (v.consensus) {
            return <circle key={i} cx={x} cy={y} r={1.5} fill="var(--brass)" opacity={0.5 + e * 0.5} />;
          }
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={1.3}
              fill="none"
              stroke="var(--muted)"
              strokeWidth={0.4}
              opacity={0.5}
            />
          );
        })}
      </svg>

      <div className="mt-1.5 flex items-center justify-center gap-4 font-mono text-[10px] text-muted">
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
    </div>
  );
}
