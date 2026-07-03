import type { Metadata } from "next";
import { Reveal } from "@/components/Reveal";
import { LinkArrow } from "@/components/LinkArrow";

const GITHUB = "https://github.com/erichare/verity";

export const metadata: Metadata = {
  title: "About — who builds Verity, and how to reach them",
  description:
    "Who builds Verity, how the project is licensed, versioned, and released, and how to get in touch. An independent, open-source forensic surface-comparison project.",
};

interface AboutLink {
  href: string;
  label: string;
}

interface AboutSection {
  title: string;
  body: React.ReactNode;
  links: AboutLink[];
}

const SECTIONS: AboutSection[] = [
  {
    title: "Who builds it",
    body: (
      <>
        Verity is built by <strong className="text-foreground">Eric Hare</strong>, a forensic
        statistician — a co-author of the automatic bullet-land matching method (Hare, Hofmann
        &amp; Carriquiry 2017, <em>Annals of Applied Statistics</em>) that Verity&rsquo;s
        striated pipeline descends from, and of the community&rsquo;s{" "}
        <code className="font-mono text-foreground/80">x3ptools</code> R package. He is the
        author of the project&rsquo;s technical white paper and its maintainer.
      </>
    ),
    links: [
      { href: "https://doi.org/10.1214/17-AOAS1080", label: "Hare, Hofmann & Carriquiry (2017)" },
      { href: "/whitepaper.pdf", label: "Technical white paper (PDF)" },
    ],
  },
  {
    title: "Independent, and saying so",
    body: (
      <>
        Verity is an independent project. It is not affiliated with, endorsed by, or developed
        in partnership with CSAFE, NIST, or Iowa State University. The research it builds on is
        public, peer-reviewed work that anyone may build on — the scientific lineage page
        traces exactly what comes from where.
      </>
    ),
    links: [{ href: "/lineage", label: "Scientific lineage" }],
  },
  {
    title: "Open source & licensing",
    body: (
      <>
        The entire platform — the Rust X3P codec, the comparison engine, the APIs, and this
        site — is developed in the open in a single repository, dual-licensed under{" "}
        <strong className="text-foreground">MIT or Apache-2.0</strong>, at your option. Bundled
        reference data carries its own upstream attribution.
      </>
    ),
    links: [
      { href: GITHUB, label: "github.com/erichare/verity" },
      { href: `${GITHUB}/blob/main/LICENSE-MIT`, label: "MIT license" },
      { href: `${GITHUB}/blob/main/LICENSE-APACHE`, label: "Apache-2.0 license" },
    ],
  },
  {
    title: "How it's versioned & released",
    body: (
      <>
        Released components are versioned and published: the X3P codec{" "}
        <code className="font-mono text-foreground/80">verity-x3p</code> (v0.2.0) ships on
        crates.io and PyPI, with changes tracked in the changelog. Citation metadata lives in
        the repository as <code className="font-mono text-foreground/80">CITATION.cff</code>.
        Every published validation number carries its exact protocol, and the repository has a
        dedicated issue template for challenging any of them.
      </>
    ),
    links: [
      { href: "https://crates.io/crates/verity-x3p", label: "crates.io" },
      { href: "https://pypi.org/project/verity-x3p/", label: "PyPI" },
      { href: `${GITHUB}/blob/main/CHANGELOG.md`, label: "Changelog" },
      { href: `${GITHUB}/blob/main/CITATION.cff`, label: "CITATION.cff" },
    ],
  },
  {
    title: "Contact",
    body: (
      <>
        There is no sales channel and no contact form. Questions, bug reports, and challenges
        to published numbers all go through GitHub — open an issue on the repository.
        Contributions are welcome and covered by the contributing guide and the Code of
        Conduct.
      </>
    ),
    links: [
      { href: `${GITHUB}/issues`, label: "GitHub issues" },
      { href: `${GITHUB}/blob/main/CONTRIBUTING.md`, label: "Contributing guide" },
      { href: `${GITHUB}/blob/main/CODE_OF_CONDUCT.md`, label: "Code of Conduct" },
    ],
  },
];

export default function AboutPage() {
  return (
    <main className="mx-auto w-full max-w-4xl px-6 pb-24 pt-28 sm:pt-36">
      <section className="rise max-w-3xl">
        <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
          <span className="h-1.5 w-1.5 rounded-full bg-brass" />
          The project
        </span>
        <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
          About <span className="accent-text">Verity</span>
        </h1>
        <p className="mt-5 text-lg leading-relaxed text-foreground/80">
          Verity is an open, domain-general engine for forensic surface comparison. It compares
          3-D surface-topography scans — bullet lands, cartridge-case breech-face impressions,
          and striated toolmarks — and reports a transparent, calibrated likelihood ratio with
          region-level attribution. It never reports a &ldquo;match&rdquo;; it reports an
          auditable weight of evidence.
        </p>
      </section>

      <div className="mt-12 space-y-5">
        {SECTIONS.map((s) => (
          <Reveal key={s.title}>
            <section className="glass rounded-2xl p-6 sm:p-7">
              <h2 className="font-display text-xl font-medium text-foreground sm:text-2xl">
                {s.title}
              </h2>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-foreground/75">
                {s.body}
              </p>
              <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1.5">
                {s.links.map((l) => {
                  const external = l.href.startsWith("http") || l.href.endsWith(".pdf");
                  return (
                    <a
                      key={l.href}
                      href={l.href}
                      {...(external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                      className="text-xs text-muted underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
                    >
                      {l.label}
                      <LinkArrow kind={external ? "external" : "right"} className="ml-1" />
                    </a>
                  );
                })}
              </div>
            </section>
          </Reveal>
        ))}
      </div>
    </main>
  );
}
