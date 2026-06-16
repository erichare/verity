import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Next 16 renamed `middleware` → `proxy`. One Next app serves two hosts:
//   verity.codes        → the app (app/page.tsx)
//   docs.verity.codes   → the science/docs (app/docs-site/*)
// The docs host is rewritten onto the internal /docs-site segment so its public URLs
// stay clean (docs.verity.codes/method, not /docs/method or /docs-site/method).
const DOCS_HOSTS = new Set([
  "docs.verity.codes",
  "docs.localhost:3000", // local dev: visit http://docs.localhost:3000
]);

export function proxy(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const { pathname } = request.nextUrl;
  const isDocsHost = DOCS_HOSTS.has(host);

  // Docs host: rewrite /<path> → /docs-site/<path> (transparent to the URL bar).
  if (isDocsHost && !pathname.startsWith("/docs-site")) {
    const url = request.nextUrl.clone();
    url.pathname = `/docs-site${pathname === "/" ? "" : pathname}`;
    return NextResponse.rewrite(url);
  }

  // App host: the internal /docs-site segment must not be reachable/indexable here —
  // strip the prefix and redirect to the real path (which then 308s to the docs host
  // via next.config redirects).
  if (!isDocsHost && pathname.startsWith("/docs-site")) {
    const url = request.nextUrl.clone();
    url.pathname = pathname.replace(/^\/docs-site/, "") || "/";
    return NextResponse.redirect(url, 308);
  }

  return NextResponse.next();
}

export const config = {
  // Skip static assets, image optimization, the metadata files, and the public PDFs
  // (which resolve identically on both hosts). Everything else flows through.
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon.svg|apple-icon.png|opengraph-image|sitemap.xml|robots.txt|.*\\.pdf$).*)",
  ],
};
