"use client";

import { useState, type ReactNode } from "react";

// Cloudflare Scrape Shield "email obfuscation" rewrites anything that looks like an address
// (e.g. the curl arg `scan=@mark.x3p`) into an obfuscated /cdn-cgi/ email-protection link in the
// server-rendered HTML — corrupting code samples for crawlers and no-JS readers. Rendering the
// `=@` adjacency as separate nodes (an isolated `@`) keeps the visible text and the clipboard
// payload byte-identical while defeating the edge scanner. Do NOT rejoin these into one string.
function renderCodeSafely(code: string): ReactNode {
  if (!code.includes("=@")) return code;
  const nodes: ReactNode[] = [];
  code.split("=@").forEach((segment, i) => {
    if (i > 0) {
      nodes.push("=");
      nodes.push(<span key={`at-${i}`}>@</span>);
    }
    nodes.push(segment);
  });
  return nodes;
}

/** A copy-to-clipboard code block, styled to match the site (mono, glass, hairline). */
export function CodeBlock({
  code,
  label,
  className,
}: {
  code: string;
  label?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable (e.g. insecure context) — fail quietly
    }
  }

  return (
    <div
      className={`group relative overflow-hidden rounded-xl border border-border bg-foreground/[0.03] ${className ?? ""}`}
    >
      {label && (
        <div className="border-b border-border px-4 py-2 font-mono text-[11px] uppercase tracking-wider text-muted">
          {label}
        </div>
      )}
      <button
        onClick={copy}
        aria-label="Copy code"
        className="absolute right-2 top-2 z-10 rounded-md border border-border bg-background/70 px-2 py-1 text-[11px] font-medium text-foreground/70 opacity-0 backdrop-blur transition hover:text-foreground focus:opacity-100 group-hover:opacity-100"
        style={label ? { top: "2.6rem" } : undefined}
      >
        {copied ? "Copied ✓" : "Copy"}
      </button>
      <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed">
        <code className="font-mono text-foreground/90">{renderCodeSafely(code)}</code>
      </pre>
    </div>
  );
}
