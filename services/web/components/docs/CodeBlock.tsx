"use client";

import { useState } from "react";

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
        <code className="font-mono text-foreground/90">{code}</code>
      </pre>
    </div>
  );
}
