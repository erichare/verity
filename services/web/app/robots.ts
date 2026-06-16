import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // The internal rewrite target must never be crawled (defense-in-depth; the
      // proxy already keeps it off the app host).
      disallow: "/docs-site/",
    },
    sitemap: "https://verity.codes/sitemap.xml",
  };
}
