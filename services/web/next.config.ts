import type { NextConfig } from "next";

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
    ];
  },
};

export default nextConfig;
