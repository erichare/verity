"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface Timeline {
  index: number; // current stage (0 … nStages-1)
  progress: number; // 0 → 1 within the current stage
  playing: boolean;
  atEnd: boolean;
  reducedMotion: boolean;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  next: () => void;
  prev: () => void;
  seekIndex: (i: number) => void;
  restart: () => void;
}

/**
 * The single timeline scalar that drives the whole theater. `pos` runs continuously over
 * [0, nStages]; the integer part is the active stage and the fraction is its progress, so
 * one rAF loop animates auto-play, while next/prev/seek snap to a stage. Honors
 * prefers-reduced-motion by never auto-playing and reporting every stage as settled.
 */
export function useTimeline(nStages: number, runKey: string, stageMs = 5400): Timeline {
  const [pos, setPos] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [reduced, setReduced] = useState(false);
  const raf = useRef(0);
  const last = useRef(0);

  useEffect(() => {
    setReduced(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
  }, []);

  // New run → restart; auto-play unless the visitor prefers reduced motion.
  useEffect(() => {
    setPos(0);
    setPlaying(!reduced && nStages > 1);
  }, [runKey, nStages, reduced]);

  useEffect(() => {
    if (!playing) return;
    last.current = 0;
    const tick = (t: number) => {
      if (!last.current) last.current = t;
      const dt = t - last.current;
      last.current = t;
      setPos((p) => {
        const np = p + dt / stageMs;
        if (np >= nStages) {
          setPlaying(false);
          return nStages;
        }
        return np;
      });
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, nStages, stageMs]);

  const index = Math.min(Math.floor(pos), nStages - 1);
  const progress = reduced ? 1 : Math.min(1, Math.max(0, pos - index));
  const atEnd = index >= nStages - 1 && progress >= 1;

  const play = useCallback(() => {
    setPos((p) => (p >= nStages ? 0 : p));
    setPlaying(true);
  }, [nStages]);
  const pause = useCallback(() => setPlaying(false), []);
  const toggle = useCallback(() => (playing ? pause() : play()), [playing, pause, play]);
  // Manual jumps land on the stage's *settled* keyframe (progress ≈ 1), so stepping shows
  // the result of each step rather than its first frame; auto-play still animates 0 → 1.
  const seekIndex = useCallback(
    (i: number) => {
      setPlaying(false);
      const clamped = Math.max(0, Math.min(nStages - 1, i));
      setPos(clamped + 0.999);
    },
    [nStages],
  );
  const next = useCallback(() => seekIndex(index + 1), [seekIndex, index]);
  const prev = useCallback(() => seekIndex(index - 1), [seekIndex, index]);
  const restart = useCallback(() => {
    setPos(0);
    setPlaying(!reduced);
  }, [reduced]);

  return {
    index,
    progress,
    playing,
    atEnd,
    reducedMotion: reduced,
    play,
    pause,
    toggle,
    next,
    prev,
    seekIndex,
    restart,
  };
}
