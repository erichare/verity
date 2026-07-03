"use client";

import { useState } from "react";

/**
 * The full 64-char split hash, accessible beyond hover: expandable in place
 * (touch + screen-reader friendly) with a copy-to-clipboard button — hash
 * equality is the benchmark's verification story, so the full value must be
 * reachable on every device.
 */
export function SplitHash({ hash }: { hash: string }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions / insecure context) — expose the
      // full hash inline instead so it can be selected manually.
      setExpanded(true);
    }
  }

  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
        aria-label={expanded ? "Collapse the split hash" : "Show the full split hash"}
        className="break-all text-left font-mono underline decoration-border underline-offset-2 transition hover:text-accent"
      >
        {expanded ? hash : `${hash.slice(0, 12)}…`}
      </button>
      <button
        type="button"
        onClick={copy}
        aria-label="Copy the full split hash to the clipboard"
        className="rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted transition hover:text-foreground"
      >
        {copied ? "copied" : "copy"}
      </button>
      <span aria-live="polite" className="sr-only">
        {copied ? "Split hash copied to clipboard" : ""}
      </span>
    </span>
  );
}
