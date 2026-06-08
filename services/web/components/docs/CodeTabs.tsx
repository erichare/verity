"use client";

import { useState } from "react";
import { CodeBlock } from "./CodeBlock";

export interface Tab {
  label: string;
  code: string;
}

/** Language-tabbed code (e.g. curl / Python / R / Rust) over a shared CodeBlock. */
export function CodeTabs({ tabs, className }: { tabs: Tab[]; className?: string }) {
  const [active, setActive] = useState(0);
  const current = tabs[active] ?? tabs[0];

  return (
    <div className={className}>
      <div role="tablist" className="mb-2 flex flex-wrap gap-1">
        {tabs.map((t, i) => (
          <button
            key={t.label}
            role="tab"
            aria-selected={i === active}
            onClick={() => setActive(i)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              i === active
                ? "bg-gradient-to-r from-indigo-500 to-cyan-400 text-slate-950"
                : "border border-border text-foreground/70 hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <CodeBlock code={current.code} />
    </div>
  );
}
