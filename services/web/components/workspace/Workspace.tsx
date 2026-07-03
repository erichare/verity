"use client";

import { useEffect, useMemo, useState } from "react";
import type { BenchResult, GalleryComparison, GallerySpecimen, MarkDomain } from "@/lib/types";
import {
  GALLERY_SPECIMENS,
  findComparison,
  getSpecimen,
  pickAny,
  pickByRelation,
} from "@/lib/gallery";
import { SpecimenGallery } from "./SpecimenGallery";
import type { SlotState } from "./SpecimenCard";
import { LabBench } from "./LabBench";

function toBenchResult(c: GalleryComparison): BenchResult {
  return {
    report: c.report,
    provenance: "gallery",
    relation: c.relation,
    source: getSpecimen(c.aId)?.source,
    signatures: c.signatures,
    calibration: c.calibration,
  };
}

/**
 * The homepage centerpiece: a curated gallery of real marks. Pick two (or hit a
 * shortcut) and the lab bench animates the calibrated likelihood ratio. Selection +
 * pairing live here; the picker and the bench are presentational.
 */
// Open on a real same-source bullet comparison so the bench shows a resolved
// likelihood ratio on first paint — arrival at the tool means seeing it work, not an
// empty picker. Falls back to any known-match pair if the gallery has no striated one.
const DEFAULT_PAIR = pickByRelation("KM", "striated") ?? pickByRelation("KM");

// The bench result for the default pair, computed synchronously so server-render
// and first client paint already show the resolved LR — the copy never contradicts
// the pre-selected slots (no "pick a second mark" flash under a filled pair).
const DEFAULT_RESULT = DEFAULT_PAIR ? toBenchResult(DEFAULT_PAIR) : null;

export function Workspace() {
  const [slotA, setSlotA] = useState<string | null>(DEFAULT_PAIR?.aId ?? null);
  const [slotB, setSlotB] = useState<string | null>(DEFAULT_PAIR?.bId ?? null);
  const [result, setResult] = useState<BenchResult | null>(DEFAULT_RESULT);
  const [surprise, setSurprise] = useState(0);

  const specA = slotA ? getSpecimen(slotA) : undefined;

  useEffect(() => {
    if (slotA && slotB) {
      const c = findComparison(slotA, slotB);
      setResult(c ? toBenchResult(c) : null);
    } else {
      setResult(null);
    }
  }, [slotA, slotB]);

  function onPick(id: string) {
    if (id === slotA) {
      setSlotA(null);
      setSlotB(null);
      return;
    }
    if (id === slotB) {
      setSlotB(null);
      return;
    }
    if (!slotA) setSlotA(id);
    else setSlotB(id);
  }

  function selectComparison(c: GalleryComparison | undefined) {
    if (!c) return;
    setSlotA(c.aId);
    setSlotB(c.bId);
  }

  function onQuick(kind: "match" | "nonmatch" | "surprise", domain: MarkDomain) {
    if (kind === "match") selectComparison(pickByRelation("KM", domain));
    else if (kind === "nonmatch") selectComparison(pickByRelation("KNM", domain));
    else {
      selectComparison(pickAny(domain, surprise));
      setSurprise((n) => n + 1);
    }
  }

  function reset() {
    setSlotA(null);
    setSlotB(null);
  }

  const cardState = useMemo(() => {
    return (spec: GallerySpecimen): SlotState => {
      if (spec.id === slotA) return "a";
      if (spec.id === slotB) return "b";
      if (specA) return specA.pairs.includes(spec.id) ? "default" : "dimmed";
      return "default";
    };
  }, [slotA, slotB, specA]);

  const aLabel = slotA ? getSpecimen(slotA)?.label : undefined;
  const bLabel = slotB ? getSpecimen(slotB)?.label : undefined;
  const revealKey = result && slotA && slotB ? `${slotA}__${slotB}` : "";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SlotBar
          aLabel={aLabel}
          bLabel={bLabel}
          onClearA={() => {
            setSlotA(slotB);
            setSlotB(null);
          }}
          onClearB={() => setSlotB(null)}
        />
        {(slotA || slotB) && (
          <button
            type="button"
            onClick={reset}
            className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground/70 transition hover:border-accent/50 hover:text-foreground"
          >
            Reset
          </button>
        )}
      </div>

      <SpecimenGallery
        specimens={GALLERY_SPECIMENS}
        cardState={cardState}
        onPick={onPick}
        onQuick={onQuick}
      />

      {result ? (
        <div className="rise border-t border-border pt-6">
          <LabBench result={result} revealKey={revealKey} aLabel={aLabel} bLabel={bLabel} />
        </div>
      ) : (
        <p className="border-t border-border pt-6 text-center text-sm text-muted">
          {slotA
            ? "Pick a second mark to compare against — or use a shortcut above."
            : "Pick two marks, or try “Same-source pair”. Every result is a real, precomputed comparison."}
        </p>
      )}
    </div>
  );
}

function SlotBar({
  aLabel,
  bLabel,
  onClearA,
  onClearB,
}: {
  aLabel?: string;
  bLabel?: string;
  onClearA: () => void;
  onClearB: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <Slot tag="A" label={aLabel} onClear={onClearA} />
      <span className="text-muted">vs</span>
      <Slot tag="B" label={bLabel} onClear={onClearB} />
    </div>
  );
}

function Slot({ tag, label, onClear }: { tag: string; label?: string; onClear: () => void }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 ${
        label ? "border-brass/40 bg-brass/[0.06] text-foreground" : "border-dashed border-border text-muted"
      }`}
    >
      <span className="flex h-4 w-4 items-center justify-center rounded-full bg-foreground/10 text-[10px] font-semibold">
        {tag}
      </span>
      <span className="max-w-[14rem] truncate">{label ?? "choose a mark"}</span>
      {label && (
        <button
          type="button"
          onClick={onClear}
          aria-label={`Clear Slot ${tag}`}
          className="text-muted transition hover:text-foreground"
        >
          ✕
        </button>
      )}
    </span>
  );
}
