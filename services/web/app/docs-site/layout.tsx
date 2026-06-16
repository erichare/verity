import type { Metadata } from "next";
import { DocsSiteNav } from "@/components/docs/DocsSiteNav";

// docs.verity.codes — the science/docs umbrella. metadataBase points social/OG at the
// docs host (the app host keeps its own in the root layout). Next only emits a
// <link rel="canonical"> when a page sets alternates.canonical, so the internal
// /docs-site segment never leaks into canonicals.
export const metadata: Metadata = {
  metadataBase: new URL("https://docs.verity.codes"),
  title: {
    default: "Verity docs — the method, validation, and API",
    template: "%s · Verity docs",
  },
  description:
    "The science behind Verity: the calibrated method, the open benchmark, the reference data catalog, and the API — for forensic examiners, statisticians, and researchers.",
};

export default function DocsSiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <DocsSiteNav />
      {children}
    </>
  );
}
