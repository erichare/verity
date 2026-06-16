import type { GallerySpecimen } from "@/lib/types";
import { Thumbnail } from "./Thumbnail";

export type SlotState = "default" | "dimmed" | "a" | "b";

/** One pickable specimen in the gallery. Lit when selectable, dimmed when it has no
 *  precomputed comparison with the current Slot A, badged A/B when chosen. */
export function SpecimenCard({
  spec,
  state,
  onPick,
}: {
  spec: GallerySpecimen;
  state: SlotState;
  onPick: (id: string) => void;
}) {
  const selected = state === "a" || state === "b";
  const dimmed = state === "dimmed";
  return (
    <button
      type="button"
      onClick={() => onPick(spec.id)}
      disabled={dimmed}
      aria-pressed={selected}
      title={dimmed ? "No precomputed comparison with Slot A — upload to compare live" : spec.label}
      className={`group relative flex w-full flex-col gap-2 rounded-xl border p-2.5 text-left transition ${
        selected
          ? "border-brass/60 bg-brass/[0.07]"
          : dimmed
            ? "cursor-not-allowed border-border opacity-40"
            : "border-border hover:border-accent/50 hover:bg-foreground/[0.03]"
      }`}
    >
      {selected && (
        <span className="absolute right-2 top-2 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-brass text-[11px] font-semibold text-[#f4f1ea]">
          {state === "a" ? "A" : "B"}
        </span>
      )}
      <Thumbnail
        grid={spec.thumb}
        signature={spec.signature}
        size={120}
        className="aspect-square w-full rounded-lg border border-border bg-foreground/[0.04]"
      />
      <div className="min-w-0">
        <p className="truncate text-xs font-medium text-foreground">{spec.label}</p>
        <p className="text-[11px] text-muted">{spec.source}</p>
      </div>
    </button>
  );
}
