import type { MetadataRoute } from "next";

const APP = "https://verity.codes";
const DOCS = "https://docs.verity.codes";
const STUDIO = "https://app.verity.codes";

// One combined sitemap (served on all three hosts) with absolute, canonical URLs.
const DOCS_PATHS = [
  "",
  "/method",
  "/why",
  "/benchmark",
  "/catalog",
  "/references",
  "/docs",
  "/lineage",
  "/about",
];

export default function sitemap(): MetadataRoute.Sitemap {
  // A single lastModified for the whole build — good enough for discovery, and it
  // moves on every deploy so search engines see a fresh signal.
  const lastModified = new Date();
  return [
    { url: `${APP}/`, priority: 1, lastModified },
    { url: `${STUDIO}/`, priority: 0.9, lastModified },
    ...DOCS_PATHS.map((p) => ({ url: `${DOCS}${p || "/"}`, priority: 0.8, lastModified })),
  ];
}
