import type { Metadata } from "next";
import { Reveal } from "@/components/Reveal";
import {
  GROUP_BLURBS,
  GROUP_LABELS,
  GROUP_ORDER,
  REFERENCES,
  referencesByGroup,
  type Reference,
} from "@/lib/references";
import { JsonLd, docsArticleJsonLd } from "@/components/seo/JsonLd";
import { LinkArrow } from "@/components/LinkArrow";

const REF_TITLE = "References — the science behind Verity";
const REF_DESC =
  "The full bibliography behind Verity: the foundational matching methods, the standards and critiques that motivated it, the public benchmark datasets and open tooling it is validated against, and the calibration statistics it borrows.";

export const metadata: Metadata = {
  title: REF_TITLE,
  description: REF_DESC,
  alternates: { canonical: "/references" },
  openGraph: {
    type: "article",
    siteName: "Verity",
    url: "/references",
    title: REF_TITLE,
    description: REF_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity — references" }],
  },
};

function RefRow({ r }: { r: Reference }) {
  return (
    <li className="border-t border-border py-4 first:border-0 first:pt-0">
      <a
        href={r.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group block"
      >
        <p className="text-sm leading-relaxed text-foreground/80">
          <span className="font-medium text-foreground">
            {r.authors} ({r.year}).
          </span>{" "}
          <span className="italic transition group-hover:text-foreground">{r.title}.</span>{" "}
          <span className="text-muted">{r.venue}.</span>
          <LinkArrow
            kind="external"
            className="ml-1 text-muted/60 transition-colors group-hover:text-accent"
          />
          {r.urlUnverified && (
            <span className="ml-2 align-middle text-[10px] uppercase tracking-wider text-muted/70">
              link to confirm
            </span>
          )}
        </p>
      </a>
      {r.relevance && (
        <p className="mt-1.5 text-xs leading-relaxed text-muted">{r.relevance}</p>
      )}
    </li>
  );
}

export default function ReferencesPage() {
  return (
    <>
      <JsonLd data={docsArticleJsonLd({ slug: "references", title: REF_TITLE, description: REF_DESC, breadcrumb: "References" })} />

      <main id="main" className="mx-auto w-full max-w-4xl px-6 pb-24 pt-28 sm:pt-36">
        <section className="rise">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            The scholarly record
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold tracking-tight sm:text-6xl">
            <span className="accent-text">References</span>
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-foreground/80">
            Verity stands on a large body of public, peer-reviewed forensic-statistics work. These are
            the methods it builds on, the field reviews that motivated it, the open datasets and tooling
            it is validated against, and the statistics it borrows. Every scientific claim on this site
            traces to one of these or to the number registry in the repository.
          </p>
        </section>

        <div className="mt-14 space-y-12">
          {GROUP_ORDER.map((group) => {
            const refs = referencesByGroup(group);
            if (!refs.length) return null;
            return (
              <Reveal key={group}>
                <section className="glass rounded-2xl p-6 sm:p-8">
                  <h2 className="font-display text-xl font-medium text-foreground sm:text-2xl">
                    {GROUP_LABELS[group]}
                  </h2>
                  <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-foreground/70">
                    {GROUP_BLURBS[group]}
                  </p>
                  <ul className="mt-5">
                    {refs.map((r) => (
                      <RefRow key={r.id} r={r} />
                    ))}
                  </ul>
                </section>
              </Reveal>
            );
          })}
        </div>

        <Reveal className="mt-12">
          <p className="text-xs leading-relaxed text-muted">
            {REFERENCES.length} references. Verity is an independent project; citation here indicates
            scientific lineage and validation targets, not endorsement or affiliation by the cited
            authors or their institutions.
          </p>
        </Reveal>
      </main>
    </>
  );
}
