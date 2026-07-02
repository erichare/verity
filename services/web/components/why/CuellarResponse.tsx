import { Reveal } from "@/components/Reveal";

/**
 * A respectful, non-defensive response to Cuellar et al. (2024). They found that
 * the black-box studies behind firearms identification do not establish its error
 * rate; Verity operationalizes exactly what they identified as missing. Cuellar
 * and co-authors are part of this community (Vanderplas co-authored bulletxtrctr,
 * a Verity benchmark baseline), so the tone is "they were right, and here is the
 * concrete answer," not rebuttal. The "They found" column stays strictly within
 * the paper; everything Verity-specific lives in the "Verity" column.
 */

interface Point {
  finding: string;
  answer: string;
}

const POINTS: Point[] = [
  {
    finding: "The black-box studies behind firearms identification do not establish a characterized error rate.",
    answer:
      "Verity reports a Cllr — a characterized calibration cost — on a named reference population, instead of an implied universal accuracy.",
  },
  {
    finding: "Inconclusive and missing responses are counted in ways that make the studies look more accurate than they are.",
    answer:
      "Verity never forces a categorical call: it reports a bounded likelihood ratio (an empirical cap on what the reference data can support), so weak evidence reads as a weak LR — not a discarded inconclusive.",
  },
  {
    finding: "Claims of validity outrun the data behind them.",
    answer:
      "Verity states its scope plainly and declines to answer outside the population it was calibrated on — a glass-box, monotone map, not a verdict.",
  },
];

export function CuellarResponse() {
  return (
    <Reveal>
      <section className="glass rounded-2xl p-6 sm:p-8">
        <div className="max-w-3xl">
          <span className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/[0.08] px-3 py-1 text-xs font-medium text-foreground/80">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            A direct response
          </span>
          <h2 className="mt-4 font-display text-2xl font-medium text-foreground sm:text-3xl">
            How Verity responds to{" "}
            <a
              href="https://doi.org/10.1093/lpr/mgae015"
              target="_blank"
              rel="noopener noreferrer"
              className="accent-text underline decoration-transparent underline-offset-4 transition hover:decoration-current"
            >
              Cuellar et&nbsp;al. (2024)
            </a>
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-foreground/80">
            Cuellar, Vanderplas, Luby &amp; Rosenblum showed that the black-box studies underpinning
            firearms identification do not establish a characterized error rate. We think they are
            right — and Verity is built to supply precisely what they found missing. This is not a
            rebuttal; it is the concrete answer their critique calls for.
          </p>
        </div>

        <div className="mt-6 grid gap-3">
          {POINTS.map((p) => (
            <div
              key={p.finding}
              className="grid gap-3 rounded-xl border border-border bg-foreground/[0.02] p-4 sm:grid-cols-2 sm:gap-5"
            >
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 shrink-0 font-mono text-xs text-muted">They found</span>
                <p className="text-sm leading-relaxed text-foreground/70">{p.finding}</p>
              </div>
              <div className="flex items-start gap-2.5 sm:border-l sm:border-border sm:pl-5">
                <span className="mt-0.5 shrink-0 font-mono text-xs text-accent">Verity</span>
                <p className="text-sm leading-relaxed text-foreground/85">{p.answer}</p>
              </div>
            </div>
          ))}
        </div>

        <p className="mt-6 max-w-3xl text-xs leading-relaxed text-muted">
          One of the critique&rsquo;s authors co-authored <code className="font-mono">bulletxtrctr</code>,
          which Verity benchmarks against — the same community, working toward the same standard of
          honesty. Verity does not claim to characterize the error rate of human examination, which
          remains unknown; it characterizes the cost of <em>its own</em> calibrated number on a stated
          reference.
        </p>
      </section>
    </Reveal>
  );
}
