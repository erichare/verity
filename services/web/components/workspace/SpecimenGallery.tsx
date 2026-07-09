"use client";

import { useState } from "react";
import type { GallerySpecimen, MarkDomain } from "@/lib/types";
import { SpecimenCard, type SlotState } from "./SpecimenCard";

const TABS: { key: MarkDomain; label: string }[] = [
  { key: "striated", label: "Bullets" },
  { key: "impressed", label: "Cartridge cases" },
  { key: "toolmark", label: "Toolmarks" },
];

const QUICK =
  "min-h-10 rounded-full border border-brass/50 bg-brass/[0.06] px-3 py-2 text-xs font-medium text-foreground/85 transition hover:border-brass hover:bg-brass/[0.12]";

/** The specimen picker: domain tabs, a grid of real-mark cards, and the on-stage
 *  shortcuts ("Same-source pair / Different-source pair / Surprise me"). Tab state is
 *  local UI; selection + pairing live in <Workspace>. */
export function SpecimenGallery({
  specimens,
  cardState,
  onPick,
  onQuick,
}: {
  specimens: GallerySpecimen[];
  cardState: (spec: GallerySpecimen) => SlotState;
  onPick: (id: string) => void;
  onQuick: (kind: "match" | "nonmatch" | "surprise", domain: MarkDomain) => void;
}) {
  const present = TABS.filter((t) => specimens.some((s) => s.domain === t.key));
  const [tab, setTab] = useState<MarkDomain>(present[0]?.key ?? "striated");
  const shown = specimens.filter((s) => s.domain === tab);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Specimen type" className="flex gap-1 rounded-full border border-control p-1">
          {present.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => {
                setTab(t.key);
                // Keep the workspace coherent across modalities: switching the
                // gallery also loads a real same-source example in that domain.
                onQuick("match", t.key);
              }}
              aria-pressed={tab === t.key}
              className={`min-h-9 rounded-full px-3 py-1.5 text-xs font-medium transition ${
                tab === t.key ? "bg-primary text-[#f4f1ea]" : "text-foreground/70 hover:text-foreground"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Quick comparison" className="flex flex-wrap gap-2">
          <button type="button" className={QUICK} onClick={() => onQuick("match", tab)}>
            Same-source pair
          </button>
          <button type="button" className={QUICK} onClick={() => onQuick("nonmatch", tab)}>
            Different-source pair
          </button>
          <button type="button" className={QUICK} onClick={() => onQuick("surprise", tab)}>
            Surprise me
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {shown.map((s) => (
          <SpecimenCard key={s.id} spec={s} state={cardState(s)} onPick={onPick} />
        ))}
      </div>
    </div>
  );
}
