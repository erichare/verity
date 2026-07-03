import { Reveal } from "@/components/Reveal";

/**
 * CSAFE / Iowa State lineage. Verity operationalizes and deploys a research
 * program it did not invent: the 2017 AOAS automatic-matching method, Song's
 * CMC line, and validation against the community's public benchmark data.
 *
 * Framed as lineage and homage — NOT as endorsement or affiliation. The
 * non-affiliation note is part of the component so it always travels with the
 * CSAFE framing.
 */

interface Cite {
  label: string;
  href: string;
}

interface Pillar {
  tag: string;
  title: string;
  body: string;
  // One or more citations; each gets its own correct link.
  cites?: Cite[];
}

const PILLARS: Pillar[] = [
  {
    tag: "The method",
    title: "Automatic bullet matching",
    body: "Verity's bullet-land pipeline descends directly from the CSAFE/Iowa State automatic-matching method — surface signatures, alignment, and a learned similarity score, validated on the community's bullet benchmarks.",
    cites: [
      {
        label: "Hare, Hofmann & Carriquiry (2017), AOAS",
        href: "https://doi.org/10.1214/17-AOAS1080",
      },
    ],
  },
  {
    tag: "The principle",
    title: "Congruent Matching Cells",
    body: "The cell-counting idea at Verity's core is Song's CMC. Verity generalizes it to Congruent Matching Regions so one pipeline spans striated and impressed marks, rather than a bespoke method per mark type.",
    cites: [
      {
        label: "Song (2015)",
        href: "https://www.nist.gov/publications/proposed-congruent-matching-cells-cmc-method-ballistic-identifications-and-evidence",
      },
      {
        label: "Song et al. (2018)",
        href: "https://doi.org/10.1016/j.forsciint.2017.12.013",
      },
    ],
  },
  {
    tag: "The evidence",
    title: "Public benchmark data",
    body: "Verity is validated against the data the community built and shares — Hamby 252/173 bullets from the open NIST NBTRD, Fadul consecutively-manufactured cartridge cases from CSAFE-ISU's open scan repository, and screwdriver toolmarks from the open tmaRks dataset.",
    cites: [
      { label: "NIST NBTRD", href: "https://tsapps.nist.gov/NRBTD/" },
      { label: "Fadul (2011)", href: "https://doi.org/10.1111/j.1556-4029.2010.01424.x" },
    ],
  },
];

export function Lineage() {
  return (
    <Reveal>
      <section className="overflow-hidden rounded-[1.45rem] bg-gradient-to-br from-brass via-primary to-brass p-[1.5px] shadow-xl shadow-[#0e2a47]/15">
        <div className="rounded-[1.35rem] bg-background p-6 sm:p-9">
          <div className="max-w-3xl">
            <span className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/[0.08] px-3 py-1 text-xs font-medium text-foreground/80">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              Lineage
            </span>
            <h2 className="mt-4 font-display text-3xl font-medium text-foreground sm:text-4xl">
              Built on the <span className="accent-text">CSAFE research program</span>
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-foreground/80 sm:text-base">
              Verity did not invent the science of forensic surface comparison — it operationalizes
              and deploys it. The methods below, developed largely within CSAFE and at Iowa State,
              are the shoulders Verity stands on. Our contribution is the production layer:
              one calibrated, explainable pipeline, an open codec, a hosted API, and reproducible
              validation on top of this research program.
            </p>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {PILLARS.map((p) => (
              <div
                key={p.title}
                className="flex flex-col rounded-2xl border border-border bg-foreground/[0.02] p-5"
              >
                <span className="text-[11px] font-medium uppercase tracking-wider text-accent">
                  {p.tag}
                </span>
                <h3 className="mt-1.5 font-display text-lg font-medium text-foreground">
                  {p.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-foreground/75">{p.body}</p>
                {p.cites && (
                  <div className="mt-auto flex flex-col gap-1 pt-3">
                    {p.cites.map((c) => (
                      <a
                        key={c.href}
                        href={c.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-muted underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
                      >
                        {c.label}{" "}
                        <span aria-hidden>↗</span>
                        <span className="sr-only">(opens in new tab)</span>
                      </a>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          <p className="mt-7 max-w-3xl border-t border-border pt-5 text-xs leading-relaxed text-muted">
            <strong className="font-medium text-foreground/70">Non-affiliation.</strong> Verity is an
            independent project and is not affiliated with, sponsored by, or endorsed by CSAFE or Iowa
            State University. References to their published research denote scientific lineage and
            validation targets only. A formal collaboration is something we would propose, not
            something that exists today.
          </p>
        </div>
      </section>
    </Reveal>
  );
}
