import type { Metadata } from "next";
import { JsonLd, docsArticleJsonLd } from "@/components/seo/JsonLd";

const METHOD_TITLE = "The method — a scan becomes a calibrated likelihood ratio";
const METHOD_DESC =
  "Step by step on real marks: leveling, signature extraction, alignment, congruent matching regions, and calibration — how Verity turns a 3-D surface scan into a calibrated likelihood ratio.";

// /method is a "use client" page (interactive heatmaps/plots) so it cannot export
// metadata itself. This layout supplies the page-specific title, description,
// canonical, and OG fields — resolving M25 (the two flagship client pages fell back
// to the docs-site default title). Relative canonical resolves against the docs-host
// metadataBase set in app/docs-site/layout.tsx → https://docs.verity.codes/method.
export const metadata: Metadata = {
  title: METHOD_TITLE,
  description: METHOD_DESC,
  alternates: { canonical: "/method" },
  openGraph: {
    type: "article",
    siteName: "Verity",
    url: "/method",
    title: METHOD_TITLE,
    description: METHOD_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity — the method, step by step" }],
  },
};

export default function MethodLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <JsonLd data={docsArticleJsonLd({ slug: "method", title: METHOD_TITLE, description: METHOD_DESC, breadcrumb: "The method" })} />
      {children}
    </>
  );
}
