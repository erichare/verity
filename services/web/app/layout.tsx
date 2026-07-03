import type { Metadata } from "next";
import { Newsreader, Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme/ThemeProvider";

// Editorial serif — display, wordmark, section headings. Courtroom/archival gravitas.
const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  display: "swap",
  axes: ["opsz"],
});

// Body & UI.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

// Data / metrics / code — LR values, hashes, endpoints. IBM Plex Mono is NOT a
// variable font on Google Fonts, so the weights must be enumerated explicitly.
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

const SITE_TITLE = "Verity — calibrated forensic surface comparison";
const SITE_DESC =
  "A domain-general, calibrated, explainable method for forensic surface comparison: a likelihood ratio with a characterized cost and region-level attribution, across striated and impressed marks.";

export const metadata: Metadata = {
  metadataBase: new URL("https://verity.codes"),
  title: SITE_TITLE,
  description: SITE_DESC,
  // Home canonical + site-level OpenGraph. The docs and app hosts set their own
  // metadataBase/canonical in their segment layouts; this covers the app host root.
  // Per-route pages that set alternates.canonical override this relative "/".
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "Verity",
    url: "/",
    title: SITE_TITLE,
    description: SITE_DESC,
    images: [{ url: "/opengraph-image", alt: SITE_TITLE }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${newsreader.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {/* Skip link: first focusable element, visually hidden until focused, so keyboard
            users can jump past the fixed nav straight to the page's <main id="main">. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-[#f4f1ea] focus:shadow-lg"
        >
          Skip to content
        </a>
        {/* Scroll-reveal needs JS to add .reveal-in; without it, content must never
            stay hidden at opacity 0 — show everything for no-JS readers. */}
        <noscript>
          <style>{`.reveal { opacity: 1 !important; transform: none !important; }`}</style>
        </noscript>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
