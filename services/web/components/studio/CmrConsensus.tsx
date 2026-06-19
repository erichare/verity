"use client";

import type { Vote } from "@/lib/studio";

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * The congruent-matching-regions moment: each window casts a vote on how to align the two
 * marks. As the stage plays, the votes that agree migrate into a tight consensus cluster
 * (brass), while the dissenters stay scattered (faint). A same-source pair locks; a
 * different-source pair never does. `progress` (0→1) drives the convergence.
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

  return (
    <svg viewBox="0 0 100 100" className={className} style={{ width: "100%", height: "100%" }}>
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
  );
}
