import type { Metadata } from "next";

// app.verity.codes — the full-screen "Studio". Its own metadataBase + title so social/OG
// point at the app host; the internal /studio segment never leaks (proxy.ts rewrites the
// app host's root onto it). Full-bleed, viewport-locked: the stage owns the screen.
export const metadata: Metadata = {
  metadataBase: new URL("https://app.verity.codes"),
  title: "Verity Studio — watch a forensic comparison, step by step",
  description:
    "A full-screen, glass-box view of Verity's calibrated surface comparison: the uploaded scan in 3-D, and every stage of the pipeline — preprocessing, alignment, congruent matching, calibration, and the bounded likelihood ratio.",
};

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return <div className="h-[100svh] overflow-hidden">{children}</div>;
}
