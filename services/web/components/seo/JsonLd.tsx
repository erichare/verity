/**
 * Server-rendered JSON-LD entity signals for search engines.
 *
 * A single component that emits a <script type="application/ld+json"> tag. It is
 * imported with a one-line insert on the pages that need structured data, so the
 * shared page files stay untouched apart from that one import + one element.
 *
 * The payloads are hand-authored schema.org objects passed in as `data` — this
 * component only serializes them. Keeping the JSON in the caller keeps each page's
 * markup factual and reviewable alongside the page it describes.
 *
 * `dangerouslySetInnerHTML` is the standard, safe way to inline JSON-LD in React:
 * the input is our own static object (never user data), and we escape the `<`
 * character so the string can never terminate the <script> element early.
 */
export function JsonLd({ data }: { data: object | readonly object[] }) {
  const json = JSON.stringify(data).replace(/</g, "\\u003c");
  return (
    <script
      type="application/ld+json"
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: json }}
    />
  );
}

const APP = "https://verity.codes";
const DOCS = "https://docs.verity.codes";
const DATA = "https://data.verity.codes";

/** The publisher/site entity — Organization + WebSite, emitted on the homepage. */
export const organizationJsonLd = [
  {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Verity",
    url: APP,
    description:
      "A domain-general, calibrated, explainable method for forensic surface comparison: a likelihood ratio with a characterized cost and region-level attribution, across striated and impressed marks.",
    sameAs: [
      "https://github.com/erichare/verity",
      "https://crates.io/crates/verity-x3p",
      "https://pypi.org/project/verity-x3p",
    ],
  },
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Verity",
    url: APP,
  },
] as const;

/**
 * The forensic-scan sources behind the reference data catalog and the benchmark.
 * Licenses and repositories are quoted from the References page (lib/references.ts)
 * so the markup stays factual and in step with the site's own citations.
 */
const CATALOG_SOURCES = [
  {
    name: "NIST NBTRD (National Ballistics Toolmark Research Database)",
    license: "https://www.usa.gov/government-works", // U.S. Government works — public domain
    repo: "https://tsapps.nist.gov/NRBTD",
  },
  {
    name: "CSAFE-ISU cartridgeCaseScans",
    license: "https://creativecommons.org/licenses/by/4.0/",
    repo: "https://github.com/CSAFE-ISU/cartridgeCaseScans",
  },
  {
    name: "tmaRks screwdriver toolmarks",
    license: "https://opensource.org/licenses/MIT",
    repo: "https://github.com/heike/tmaRks",
  },
  {
    name: "CSAFE multi-instrument virtual comparison kits (Figshare)",
    license: "https://creativecommons.org/licenses/by/4.0/",
    repo: "https://doi.org/10.6084/m9.figshare.30854414",
  },
];

/** Dataset markup for the reference data catalog (/catalog on the docs host). */
export const catalogDatasetJsonLd = {
  "@context": "https://schema.org",
  "@type": "Dataset",
  name: "Verity reference data catalog",
  description:
    "A content-addressed catalog of 3-D forensic surface scans — bullet lands, cartridge-case marks, and toolmarks — harvested and labeled from public research repositories, downloadable as raw X3P (ISO 25178-72).",
  url: `${DOCS}/catalog`,
  license: CATALOG_SOURCES.map((s) => s.license),
  isBasedOn: CATALOG_SOURCES.map((s) => s.repo),
  distribution: CATALOG_SOURCES.map((s) => ({
    "@type": "DataDownload",
    encodingFormat: "application/x-x3p",
    contentUrl: DATA,
    name: s.name,
    license: s.license,
  })),
};

/** Dataset markup for the frozen open benchmark (/benchmark on the docs host). */
export const benchmarkDatasetJsonLd = {
  "@context": "https://schema.org",
  "@type": "Dataset",
  name: "Verity open forensic-comparison benchmark",
  description:
    "A frozen, source-disjoint benchmark for calibrated forensic-comparison likelihood ratios across bullet lands, cartridge breech faces, and toolmarks — scored on Cllr, calibration loss, and AUC, with a downloadable replication kit.",
  url: `${DOCS}/benchmark`,
  license: CATALOG_SOURCES.map((s) => s.license),
  isBasedOn: CATALOG_SOURCES.map((s) => s.repo),
  distribution: {
    "@type": "DataDownload",
    encodingFormat: "application/zip",
    contentUrl: DATA,
    name: "Verity benchmark replication kit",
  },
};

/**
 * TechArticle + BreadcrumbList for a docs-host content page. `slug` is the public
 * path segment (e.g. "method"); the breadcrumb roots at the docs host home.
 */
export function docsArticleJsonLd(opts: {
  slug: string;
  title: string;
  description: string;
  breadcrumb: string;
}): object[] {
  const url = `${DOCS}/${opts.slug}`;
  return [
    {
      "@context": "https://schema.org",
      "@type": "TechArticle",
      headline: opts.title,
      description: opts.description,
      url,
      isPartOf: { "@type": "WebSite", name: "Verity", url: APP },
      publisher: { "@type": "Organization", name: "Verity", url: APP },
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Docs", item: DOCS },
        { "@type": "ListItem", position: 2, name: opts.breadcrumb, item: url },
      ],
    },
  ];
}
