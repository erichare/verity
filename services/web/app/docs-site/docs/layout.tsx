import type { Metadata } from "next";
import { JsonLd, docsArticleJsonLd } from "@/components/seo/JsonLd";

// Canonical + OpenGraph + TechArticle markup for /docs, supplied via a NEW layout so
// the page's existing metadata const (recently edited by another PR) only needs its
// title touched. Layout metadata is merged with the page's, so title/description set
// on the page win; here we add only the fields the page doesn't set.
const DOCS_TITLE = "Use Verity — quickstart, API, and architecture";
const DOCS_DESC =
  "Use Verity: the calibrated likelihood-ratio comparison API, the native X3P (ISO 25178-72) codec for Rust/Python/R, the data catalog, and the core concepts (LR, Cllr, Congruent Matching Regions).";

export const metadata: Metadata = {
  alternates: { canonical: "/docs" },
  openGraph: {
    type: "article",
    siteName: "Verity",
    url: "/docs",
    title: DOCS_TITLE,
    description: DOCS_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity — use Verity" }],
  },
};

export default function DocsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <JsonLd
        data={docsArticleJsonLd({
          slug: "docs",
          title: DOCS_TITLE,
          description: DOCS_DESC,
          breadcrumb: "Use Verity",
        })}
      />
      {children}
    </>
  );
}
