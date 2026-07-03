import type { Metadata } from "next";
import { JsonLd, catalogDatasetJsonLd } from "@/components/seo/JsonLd";

// /catalog is a "use client" page (live Supabase-backed browsing) so it cannot export
// metadata itself. This layout supplies the page-specific title, description,
// canonical, and OG fields — resolving M25. Relative canonical resolves against the
// docs-host metadataBase → https://docs.verity.codes/catalog.
export const metadata: Metadata = {
  title: "The data catalog — forensic scans behind the references",
  description:
    "Browse the 3-D forensic scans behind Verity's references — striated bullet lands, impressed cartridge marks, and toolmarks — content-addressed and downloadable as raw X3P.",
  alternates: { canonical: "/catalog" },
  openGraph: {
    type: "website",
    siteName: "Verity",
    url: "/catalog",
    title: "The data catalog — forensic scans behind the references",
    description:
      "Browse the 3-D forensic scans behind Verity's references — striated, impressed, and toolmark — content-addressed and downloadable as raw X3P.",
    images: [{ url: "/opengraph-image", alt: "Verity — the reference data catalog" }],
  },
};

export default function CatalogLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <JsonLd data={catalogDatasetJsonLd} />
      {children}
    </>
  );
}
