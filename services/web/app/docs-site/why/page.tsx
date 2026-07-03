import type { Metadata } from "next";
import { Reveal } from "@/components/Reveal";
import { Benchmarks } from "@/components/why/Benchmarks";
import { Lineage } from "@/components/why/Lineage";
import { CuellarResponse } from "@/components/why/CuellarResponse";
import { JsonLd, docsArticleJsonLd } from "@/components/seo/JsonLd";
import { LinkArrow } from "@/components/LinkArrow";

const WHY_TITLE = "Why Verity — what was missing";
const WHY_DESC =
  "Forensic comparison has excellent, hard-won tools. Verity exists to close gaps none of them close on their own: one calibrated, explainable, open method across mark types.";

export const metadata: Metadata = {
  title: WHY_TITLE,
  description: WHY_DESC,
  alternates: { canonical: "/why" },
  openGraph: {
    type: "article",
    siteName: "Verity",
    url: "/why",
    title: WHY_TITLE,
    description: WHY_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity — why this exists" }],
  },
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

const GLYPH: Record<Mark, { c: string; cls: string; sr: string }> = {
  y: { c: "✓", cls: "text-accent", sr: "yes" },
  p: { c: "◐", cls: "text-muted", sr: "partial" },
  n: { c: "✕", cls: "text-foreground/65", sr: "no" },
};

function Cell({ m }: { m: Mark }) {
  return (
    <span className={`text-base ${GLYPH[m].cls}`}>
      <span aria-hidden>{GLYPH[m].c}</span>
      <span className="sr-only">{GLYPH[m].sr}</span>
    </span>
  );
}

function Matrix() {
  return (
    <div className="glass overflow-x-auto rounded-2xl p-2 sm:p-4">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <caption className="sr-only">
          Capability comparison of forensic mark-comparison approaches
        </caption>
        <thead>
          <tr className="text-xs uppercase tracking-wider text-muted">
            <th scope="col" className="px-3 py-3 text-left font-medium">Approach</th>
            {CAPS.map((c) => (
              <th key={c} scope="col" className="px-2 py-3 text-center font-medium">
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
              <th scope="row" className="px-3 py-3 text-left font-normal">
                <div className={`font-medium ${r.verity ? "accent-text" : "text-foreground"}`}>
                  {r.href ? (
                    <a href={r.href} target="_blank" rel="noopener noreferrer" className="hover:text-accent">
                      {r.name}
                      <LinkArrow kind="external" className="ml-1" />
                    </a>
                  ) : (
                    r.name
                  )}
                </div>
                <div className="text-xs font-normal text-muted">{r.note}</div>
              </th>
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
        caveats · <span className="text-foreground/65">✕</span> no. A high-level summary; each tool is
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
      <JsonLd data={docsArticleJsonLd({ slug: "why", title: WHY_TITLE, description: WHY_DESC, breadcrumb: "Why Verity" })} />

      <main id="main" className="mx-auto w-full max-w-4xl px-6 pb-24 pt-28 sm:pt-36">
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

        {/* Lineage — Verity operationalizes the CSAFE research program. */}
        <div className="mt-12 sm:mt-16">
          <Lineage />
        </div>

        <Reveal className="mt-16">
          <Matrix />
        </Reveal>

        <Reveal className="mt-16">
          <h2
            id="benchmarks"
            className="scroll-mt-24 font-display text-2xl font-medium text-foreground sm:text-3xl"
          >
            Measured against the specialists, on their home turf
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/80">
            A capability table is a claim; this is the measurement — and it is deliberately the hardest
            kind. Each specialist is run on the data it was built for; Verity is held to the{" "}
            <em>same</em> scans under a source-disjoint split (no barrel, slide, or tool appears in
            both train and test), with the exact scorer and protocol labeled on each row. Every row is
            scored per dataset and{" "}
            <strong className="text-foreground">never pooled across makes</strong>, on two axes:{" "}
            <strong className="text-foreground">AUC</strong> (can it tell same-source from
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
            highlighted. Every row shares Verity&rsquo;s preprocessing-and-calibration pipeline, and
            the scorer behind each Verity figure is labeled on its row: bullet rows use the production
            CMR score; the cartridge and tmaRks rows quote the frozen public benchmarks, so they match
            the{" "}
            <a href="/benchmark" className="text-accent hover:underline">
              open benchmark
            </a>{" "}
            and{" "}
            <a href="/method" className="text-accent hover:underline">
              the method page
            </a>{" "}
            exactly; the Ames Lab row is a non-deployed proof scorer kept for the Chumbley comparison.
            The trained specialists lead on their home sets — bulletxtrctr on bullets, cmcR on Fadul —
            as expected: Verity&rsquo;s contribution is the calibrated, bounded, deployable LR layer,
            not a better matcher. We report the losses alongside the wins on purpose; every figure here
            traces to a protocol-labeled row in the{" "}
            <a
              href="https://github.com/erichare/verity/blob/main/docs/headline-numbers.md"
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent hover:underline"
            >
              numbers registry
            </a>
            .
          </p>
        </Reveal>

        <Reveal className="mt-16">
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            The four gaps
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/80">
            Two decades of review — the{" "}
            <a
              href="https://doi.org/10.17226/12589"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
            >
              National Research Council (2009)
            </a>{" "}
            and{" "}
            <a
              href="https://obamawhitehouse.archives.gov/sites/default/files/microsites/ostp/PCAST/pcast_forensic_science_report_final.pdf"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
            >
              PCAST (2016)
            </a>{" "}
            — and recent work by{" "}
            <a
              href="https://doi.org/10.1093/lpr/mgae015"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
            >
              Cuellar et&nbsp;al. (2024)
            </a>{" "}
            converge on the same shortfalls.
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
            (Cllr), the standard from forensic speaker comparison (
            <a
              href="https://doi.org/10.1016/j.csl.2005.08.001"
              target="_blank"
              rel="noopener noreferrer"
              className="underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
            >
              Brümmer &amp; du Preez, 2006
            </a>
            ). Verity reports exactly that, bounded to what the reference data can support.
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

        {/* Cuellar et al. (2024) — the critique, and Verity's concrete answer. */}
        <div className="mt-16">
          <CuellarResponse />
        </div>

        {/* What the courts are asking for — primary citations only; no legal advice. */}
        <Reveal className="mt-16">
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            What the courts are asking for
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/80">
            The same demands now arrive from the bench. Three primary sources frame what a forensic
            comparison method must show before its conclusions reach a jury:
          </p>
        </Reveal>
        <div className="mt-6 grid gap-5 sm:grid-cols-3">
          <Gap n="1993" title="Daubert v. Merrell Dow">
            <em>Daubert v. Merrell Dow Pharmaceuticals</em>, 509 U.S. 579 (1993) made trial judges
            gatekeepers of expert evidence, weighing testability, peer review, known or potential
            error rates, and controlling standards.
          </Gap>
          <Gap n="2023" title="FRE 702, as amended">
            Federal Rule of Evidence 702, amended December 1, 2023, makes explicit that the
            proponent must show it is more likely than not that the testimony reflects a reliable
            application of reliable methods — and that the expert&rsquo;s opinion stays within what
            the methodology can support.
          </Gap>
          <Gap n="2023" title="Abruquah v. Maryland">
            In <em>Abruquah v. Maryland</em>, 484 Md. 64 (2023), Maryland&rsquo;s highest court held
            that a firearms examiner could not testify that crime-scene bullets were fired from a
            particular gun — the underlying studies did not support an unqualified source
            identification.
          </Gap>
        </div>
        <p className="mt-4 max-w-2xl text-xs leading-relaxed text-muted">
          None of this is legal advice, and no court has evaluated Verity itself. It is the standard
          Verity is engineered against: a calibrated likelihood ratio with a characterized cost
          (C<sub>llr</sub>) on a named reference population, bounded to what that reference can
          support — never an unqualified &ldquo;match.&rdquo;
        </p>

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
                href="https://verity.codes/#compare"
                className="rounded-full bg-primary px-6 py-3 text-sm font-semibold text-[#f4f1ea] shadow-lg shadow-[#0e2a47]/20 transition hover:opacity-90"
              >
                Try a comparison<LinkArrow className="ml-1" />
              </a>
            </div>
          </div>
        </Reveal>
      </main>
    </>
  );
}
