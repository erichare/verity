import type { MetadataRoute } from "next";

const APP = "https://verity.codes";
const DOCS = "https://docs.verity.codes";

// One combined sitemap (served on both hosts) with absolute URLs.
const DOCS_PATHS = [
  "",
  "/method",
  "/why",
  "/benchmark",
  "/catalog",
  "/references",
  "/docs",
  "/lineage",
];

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${APP}/`, priority: 1 },
    ...DOCS_PATHS.map((p) => ({ url: `${DOCS}${p || "/"}`, priority: 0.8 })),
  ];
}
