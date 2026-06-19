"use client";

import type { Stage } from "@/lib/studio";

function PlayIcon({ playing }: { playing: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      {playing ? (
        <>
          <rect x="6" y="5" width="4" height="14" rx="1" />
          <rect x="14" y="5" width="4" height="14" rx="1" />
        </>
      ) : (
        <path d="M8 5v14l11-7z" />
      )}
    </svg>
  );
}

/**
 * The spine of the experience: the labeled pipeline stages on one timeline, with transport
 * controls. The active node fills with the navy→brass gradient, completed nodes are solid,
 * upcoming are hollow. Clicking a node jumps to that stage; the rail is keyboard-navigable.
 */
export function TimelineRail({
  stages,
  index,
  progress,
  playing,
  onToggle,
  onSeek,
  onRestart,
}: {
  stages: Stage[];
  index: number;
  progress: number;
  playing: boolean;
  onToggle: () => void;
  onSeek: (i: number) => void;
  onRestart: () => void;
}) {
  return (
    <div className="flex items-center gap-4 px-4 py-3 sm:px-6">
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onToggle}
          aria-label={playing ? "Pause" : "Play"}
          className="flex h-9 w-9 items-center justify-center rounded-full text-foreground transition hover:bg-foreground/10"
        >
          <PlayIcon playing={playing} />
        </button>
        <button
          type="button"
          onClick={onRestart}
          aria-label="Restart"
          className="flex h-9 w-9 items-center justify-center rounded-full text-muted transition hover:bg-foreground/10 hover:text-foreground"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
            <path d="M3 3v5h5" />
          </svg>
        </button>
      </div>

      <ol
        className="flex flex-1 items-center"
        role="slider"
        aria-label="Pipeline stage"
        aria-valuemin={1}
        aria-valuemax={stages.length}
        aria-valuenow={index + 1}
        aria-valuetext={`Stage ${index + 1} of ${stages.length} — ${stages[index]?.label}`}
        tabIndex={0}
      >
        {stages.map((s, i) => {
          const done = i < index;
          const active = i === index;
          return (
            <li key={s.id} className="flex flex-1 items-center last:flex-none">
              <button
                type="button"
                onClick={() => onSeek(i)}
                aria-current={active ? "step" : undefined}
                className="group flex flex-col items-center gap-1"
                title={s.label}
              >
                <span
                  className={`block rounded-full transition-all ${
                    active
                      ? "h-3 w-3 bg-[linear-gradient(100deg,var(--accent),var(--brass))] ring-2 ring-brass/30"
                      : done
                        ? "h-2 w-2 bg-accent"
                        : "h-2 w-2 border border-foreground/30 bg-transparent group-hover:border-foreground/60"
                  }`}
                />
                <span
                  className={`hidden whitespace-nowrap font-mono text-[9px] uppercase tracking-wide sm:block ${
                    active ? "text-brass" : "text-muted/70 group-hover:text-foreground/70"
                  }`}
                >
                  {s.label}
                </span>
              </button>
              {i < stages.length - 1 && (
                <span className="mx-1 h-px flex-1 bg-border sm:mx-1.5">
                  <span
                    className="block h-px bg-accent transition-all"
                    style={{ width: done ? "100%" : active ? `${progress * 100}%` : "0%" }}
                  />
                </span>
              )}
            </li>
          );
        })}
      </ol>

      <span className="hidden font-mono text-[10px] text-muted sm:block">
        {index + 1} / {stages.length}
      </span>
    </div>
  );
}
