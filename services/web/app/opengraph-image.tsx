import { ImageResponse } from "next/og";

export const alt = "Verity — calibrated forensic surface comparison";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The Evidence seal, full-bleed navy with a brass ring + converging-striae "V",
// inlined as a data URI so the OG card needs no external image fetch.
const SEAL = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#c9a063"/><stop offset="0.5" stop-color="#a9803e"/><stop offset="1" stop-color="#8a6630"/>
  </linearGradient></defs>
  <rect x="0" y="0" width="512" height="512" rx="96" fill="#0e2a47"/>
  <circle cx="256" cy="256" r="186" fill="none" stroke="url(#b)" stroke-width="10"/>
  <circle cx="256" cy="256" r="168" fill="none" stroke="url(#b)" stroke-width="3" stroke-opacity="0.8"/>
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M 176 168 L 256 330 L 336 168" stroke="#e8e2d4" stroke-opacity="0.28" stroke-width="10"/>
    <path d="M 200 168 L 256 312 L 312 168" stroke="#e8e2d4" stroke-opacity="0.5" stroke-width="12"/>
    <path d="M 224 168 L 256 296 L 288 168" stroke="url(#b)" stroke-width="22"/>
  </g>
  <circle cx="256" cy="300" r="15" fill="#c9a063"/>
  <circle cx="256" cy="300" r="15" fill="none" stroke="#0e2a47" stroke-width="3"/>
</svg>`;

const SEAL_DATA_URI = `data:image/svg+xml;utf8,${encodeURIComponent(SEAL)}`;

// Fetch the Newsreader serif for the wordmark. Wrapped so an offline build falls
// back to the default font rather than failing.
async function loadNewsreader(): Promise<ArrayBuffer | null> {
  try {
    const css = await fetch(
      "https://fonts.googleapis.com/css2?family=Newsreader:wght@600",
      // An old UA makes Google serve a .ttf (Satori can't read woff2).
      { headers: { "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3)" } },
    ).then((r) => r.text());
    const url = css.match(/src:\s*url\((.+?)\)\s*format/)?.[1];
    if (!url) return null;
    return await fetch(url).then((r) => r.arrayBuffer());
  } catch {
    return null;
  }
}

export default async function Image() {
  const newsreader = await loadNewsreader();
  const serif = newsreader ? "Newsreader" : "serif";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 80,
          background: "#f4f1ea",
          color: "#13243a",
          border: "16px solid #0e2a47",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={SEAL_DATA_URI} width={128} height={128} alt="" />
          <div style={{ fontSize: 104, fontWeight: 600, color: "#0e2a47", fontFamily: serif }}>
            Verity
          </div>
        </div>
        <div style={{ fontSize: 44, marginTop: 36, color: "#13243a", fontFamily: serif }}>
          Forensic marks, weighed as evidence.
        </div>
        <div style={{ fontSize: 26, marginTop: 16, color: "#5a6677" }}>
          A calibrated likelihood ratio with a characterized cost — verity.codes
        </div>
      </div>
    ),
    {
      ...size,
      fonts: newsreader
        ? [{ name: "Newsreader", data: newsreader, weight: 600, style: "normal" }]
        : undefined,
    },
  );
}
