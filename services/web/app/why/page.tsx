import type { Metadata } from "next";
import { Reveal } from "@/components/Reveal";
import { Benchmarks } from "@/components/why/Benchmarks";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export const metadata: Metadata = {
  title: "Why Verity — what was missing",
  description:
    "Forensic comparison has excellent, hard-won tools. Verity exists to close gaps none of them close on their own: one calibrated, explainable, open method across mark types.",
};

const CAPS = ["Striated", "Impressed", "One method", "Calibrated LR", "Attribution", "Open"];

type Mark = "y" | "p" | "n";
interface Row {
  name: string;
  note: string;
  href?: string;
  cells: Mark[];
  verity?: boolean;
}

const ROWS: Row[] = [
  { name: "Trained examiner", note: "the status quo", cells: ["y", "y", "y", "n", "p", "n"] },
  {
    name: "bulletxtrctr",
    note: "bullet lands · Hare et al. 2017",
    href: "https://doi.org/10.1214/17-AOAS1080",
    cells: ["y", "n", "n", "p", "p", "y"],
  },
  {
    name: "CMC / cmcR",
    note: "breech faces · Song 2013",
    href: "https://www.nist.gov/publications/proposed-congruent-matching-cells-cmc-method-ballistic-identifications-and-evidence",
    cells: ["n", "y", "n", "p", "y", "y"],
  },
  { name: "Chumbley score", note: "striated toolmarks", cells: ["y", "n", "p", "p", "n", "p"] },
  { name: "Deep-learning match", note: "raw similarity score", cells: ["y", "y", "p", "n", "n", "n"] },
  { name: "Verity", note: "one calibrated method", cells: ["y", "y", "y", "y", "y", "y"], verity: true },
];

const GLYPH: Record<Mark, { c: string; cls: string }> = {
  y: { c: "✓", cls: "text-accent" },
  p: { c: "◐", cls: "text-muted" },
  n: { c: "✕", cls: "text-foreground/20" },
};

function Cell({ m }: { m: Mark }) {
  return <span className={`text-base ${GLYPH[m].cls}`}>{GLYPH[m].c}</span>;
}

function Matrix() {
  return (
    <div className="glass overflow-x-auto rounded-2xl p-2 sm:p-4">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wider text-muted">
            <th className="px-3 py-3 text-left font-medium">Approach</th>
            {CAPS.map((c) => (
              <th key={c} className="px-2 py-3 text-center font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((r) => (
            <tr
              key={r.name}
              className={`border-t border-border ${r.verity ? "rounded-lg bg-accent/[0.07]" : ""}`}
            >
              <td className="px-3 py-3">
                <div className={`font-medium ${r.verity ? "accent-text" : "text-foreground"}`}>
                  {r.href ? (
                    <a href={r.href} target="_blank" rel="noopener noreferrer" className="hover:text-accent">
                      {r.name} ↗
                    </a>
                  ) : (
                    r.name
                  )}
                </div>
                <div className="text-xs text-muted">{r.note}</div>
              </td>
              {r.cells.map((m, i) => (
                <td key={i} className="px-2 py-3 text-center">
                  <Cell m={m} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 pt-3 text-xs text-muted">
        <span className="text-accent">✓</span> yes · <span className="text-muted">◐</span> partial / with
        caveats · <span className="text-foreground/30">✕</span> no. A high-level summary; each tool is
        excellent at what it was built for.
      </p>
    </div>
  );
}

function Gap({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <Reveal className="glass rounded-2xl p-6 sm:p-7">
      <div className="font-display text-sm font-semibold text-accent">{n}</div>
      <h3 className="mt-1 font-display text-xl font-medium text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-foreground/80">{children}</p>
    </Reveal>
  );
}

export default function WhyPage() {
  return (
    <>
      <header className="fixed inset-x-0 top-0 z-30">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <a href="/" className="font-display text-xl font-semibold tracking-tight">
            <span className="accent-text">Verity</span>
          </a>
          <div className="flex items-center gap-5">
            <a href="/method" className="text-sm text-foreground/70 transition hover:text-foreground">
              Method
            </a>
            <a href="/#compare" className="text-sm text-foreground/70 transition hover:text-foreground">
              Compare
            </a>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl px-6 pb-24 pt-28 sm:pt-36">
        <section className="rise">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Why it was necessary
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold tracking-tight sm:text-6xl">
            Standing on <span className="accent-text">good work</span>
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-foreground/80">
            Forensic surface comparison already has excellent, hard-won tools — many open-source, and
            several that Verity builds directly on. So why a new one? Not because the others are wrong,
            but because the field&rsquo;s own reviews identified gaps that no single existing tool
            closes. Verity is the attempt to close all of them at once.
          </p>
        </section>

        <Reveal className="mt-12">
          <Matrix />
        </Reveal>

        <Reveal className="mt-16">
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            Measured against the specialists
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/80">
            A capability table is a claim; this is the measurement. On each specialist&rsquo;s home
            turf — the <em>same</em> scans, the same source-disjoint split — Verity is scored on two
            axes: <strong className="text-foreground">AUC</strong> (can it tell same-source from
            different-source apart?) and the forensic{" "}
            <strong className="text-foreground">
              C<sub>llr</sub>
            </strong>{" "}
            (is the weight of evidence well-calibrated? 0 is perfect, 1 is useless). These are real
            results — including where Verity trails.
          </p>
          <Benchmarks />
          <p className="mt-4 max-w-2xl text-xs leading-relaxed text-muted">
            Higher AUC and lower C<sub>llr</sub> are better; the stronger figure in each pair is
            highlighted. One Verity pipeline produces every row. The cartridge (10 slides) and toolmark
            (7 tools) sets are deliberately small, hardest-case benchmarks, and bulletxtrctr&rsquo;s
            random forest was trained on Hamby-family data, so its Hamby figure is near in-sample — the
            honest comparison is out-of-domain, where an untrained, stable calibration shows its worth.
          </p>
        </Reveal>

        <Reveal className="mt-16">
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            The four gaps
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/80">
            Two decades of review — the National Research Council (2009) and PCAST (2016) — and recent
            work by Cuellar et&nbsp;al. (2024) converge on the same shortfalls.
          </p>
        </Reveal>

        <div className="mt-6 grid gap-5 sm:grid-cols-2">
          <Gap n="01" title="One method, not many">
            Bullets, cartridges, and toolmarks have each grown their own hand-engineered pipeline —
            the field reinvents feature extraction per mark type. Verity generalizes the Congruent
            Matching Cells idea to arbitrary marks (Congruent Matching Regions): striated and impressed
            flow through one pipeline, differing only in the registration group.
          </Gap>
          <Gap n="02" title="A likelihood ratio, not a score">
            A random-forest matchscore, a CMC count, a U-statistic — none is a weight of evidence. The
            reportable answer should be a <em>calibrated</em> likelihood ratio with a characterized cost
            (Cllr), the standard from forensic speaker comparison (Brümmer &amp; du Preez, 2006). Verity
            reports exactly that, bounded to what the reference data can support.
          </Gap>
          <Gap n="03" title="Glass-box, not black-box">
            Recent deep networks beat classical methods on raw discrimination — but emit an
            uncalibrated score, no region-level attribution, and an architecture that invites
            source-code litigation. Verity keeps the decision a monotone, bounded transform of the
            score and shows the exact regions that drove it, so the result is auditable no matter how
            the score was computed.
          </Gap>
          <Gap n="04" title="Honest about scope">
            Cuellar et&nbsp;al. (2024) found that <em>no</em> forensic firearm discipline has a
            characterized error rate. Verity doesn&rsquo;t claim a universal accuracy; it reports Cllr on
            a <em>named</em> reference population and states its scope plainly — and refuses to answer
            outside the data it was calibrated on.
          </Gap>
        </div>

        <Reveal className="mt-20 sm:mt-28">
          <div className="glass rounded-2xl p-8 text-center">
            <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
              Built on the field, not against it
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-foreground/80">
              Verity generalizes CMC, borrows its calibration from speaker detection, and validates on
              the very datasets the community built — Hamby, NIST, and others. It does not replace the
              examiner; it hands them a transparent, calibrated number they can stand behind. That is
              what was missing, and why Verity exists.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <a
                href="/method"
                className="glass rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
              >
                See how it works
              </a>
              <a
                href="/#compare"
                className="rounded-full bg-gradient-to-r from-indigo-500 via-sky-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:opacity-90"
              >
                Try a comparison →
              </a>
            </div>
          </div>
        </Reveal>
      </main>
    </>
  );
}
