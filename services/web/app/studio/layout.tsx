import type { Metadata } from "next";

// app.verity.codes — the full-screen "Studio". Its own metadataBase + title so social/OG
// point at the app host; the internal /studio segment never leaks (proxy.ts rewrites the
// app host's root onto it). Full-bleed, viewport-locked: the stage owns the screen.
const STUDIO_TITLE = "Verity Studio — watch a forensic comparison, step by step";
const STUDIO_DESC =
  "A full-screen, glass-box view of Verity's calibrated surface comparison: curated specimens or your own scan in 3-D, and every stage of the pipeline — preprocessing, alignment, congruent matching, calibration, and the bounded likelihood ratio.";

export const metadata: Metadata = {
  metadataBase: new URL("https://app.verity.codes"),
  title: STUDIO_TITLE,
  description: STUDIO_DESC,
  // Canonicalize to the public app-host root (proxy.ts rewrites "/" → "/studio"; the
  // internal segment must never be the canonical). Relative "/" resolves against the
  // app-host metadataBase above → https://app.verity.codes/.
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Verity",
    url: "/",
    title: STUDIO_TITLE,
    description: STUDIO_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity Studio — the pipeline, step by step" }],
  },
};

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return <div className="h-[100svh] overflow-hidden">{children}</div>;
}
