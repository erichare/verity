import type { NextConfig } from "next";

// Content that moved from verity.codes/<x> to docs.verity.codes/<x>. Old links 308
// (permanent, method-preserving) to the docs host so search engines re-index cleanly.
const DOCS_SEGMENTS = [
  "method",
  "why",
  "benchmark",
  "catalog",
  "references",
  "docs",
  "partnership",
];

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // Canonical host: 308 www.verity.codes -> verity.codes (path preserved).
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.verity.codes" }],
        destination: "https://verity.codes/:path*",
        permanent: true,
      },
      // The Studio lives on its own host. A shareable verity.codes/studio link 308s to
      // app.verity.codes (which serves the studio at its root via proxy.ts).
      {
        source: "/studio",
        has: [{ type: "host", value: "verity.codes" }],
        destination: "https://app.verity.codes",
        permanent: true,
      },
      {
        source: "/studio/:path*",
        has: [{ type: "host", value: "verity.codes" }],
        destination: "https://app.verity.codes/:path*",
        permanent: true,
      },
      // Moved content: verity.codes/<seg>(/...) -> docs.verity.codes/<seg>(/...).
      // Host-gated so they only fire on the app host (the docs host serves the page).
      ...DOCS_SEGMENTS.flatMap((seg) => [
        {
          source: `/${seg}`,
          has: [{ type: "host" as const, value: "verity.codes" }],
          destination: `https://docs.verity.codes/${seg}`,
          permanent: true,
        },
        {
          source: `/${seg}/:path*`,
          has: [{ type: "host" as const, value: "verity.codes" }],
          destination: `https://docs.verity.codes/${seg}/:path*`,
          permanent: true,
        },
      ]),
    ];
  },
};

export default nextConfig;
