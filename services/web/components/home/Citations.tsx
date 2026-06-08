import { REFERENCES, type Reference } from "@/lib/references";

/**
 * The scholarly record behind the homepage claim — kept collapsed by default.
 *
 * Driven from lib/references.ts (the single source of truth). The homepage
 * shows a focused subset; the full, grouped bibliography lives at /references.
 */

// The core citations surfaced on the homepage, in display order.
const HOME_IDS = [
  "nrc-2009",
  "pcast-2016",
  "cuellar-2024",
  "song-2013",
  "hare-2017",
  "brummer-2006",
] as const;

const byId = new Map<string, Reference>(REFERENCES.map((r) => [r.id, r]));
export const HOME_CITATIONS: Reference[] = HOME_IDS.map((id) => byId.get(id)).filter(
  (r): r is Reference => Boolean(r),
);

export function Citations() {
  return (
    <ul className="mt-4 space-y-1.5 text-xs text-muted">
      {HOME_CITATIONS.map((ref) => (
        <li key={ref.id} className="leading-relaxed">
          <a
            href={ref.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline transition hover:text-foreground/80"
          >
            <span className="text-foreground/80 underline decoration-border underline-offset-2 transition group-hover:decoration-accent group-hover:text-accent">
              {ref.authors} ({ref.year})
            </span>{" "}
            — <span className="italic">{ref.title}.</span>
            <span aria-hidden className="ml-0.5 not-italic text-muted/60 transition group-hover:text-accent">
              ↗
            </span>
          </a>
        </li>
      ))}
      <li className="pt-1.5">
        <a
          href="/references"
          className="text-foreground/70 underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
        >
          Full bibliography ({REFERENCES.length}) →
        </a>
      </li>
    </ul>
  );
}
