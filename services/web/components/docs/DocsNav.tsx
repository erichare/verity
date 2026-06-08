"use client";

import { useEffect, useState } from "react";

export interface NavSection {
  id: string;
  label: string;
}

/** Sticky sidebar with scroll-spy — highlights the section currently in view. */
export function DocsNav({ sections }: { sections: NavSection[] }) {
  const [active, setActive] = useState(sections[0]?.id ?? "");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        // Prefer the topmost section currently intersecting the focus band.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 },
    );
    for (const s of sections) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [sections]);

  return (
    <nav className="sticky top-24 hidden max-h-[calc(100vh-7rem)] overflow-y-auto lg:block">
      <p className="mb-3 font-mono text-[11px] uppercase tracking-wider text-muted">On this page</p>
      <ul className="space-y-1 border-l border-border">
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              className={`-ml-px block border-l py-1 pl-4 text-sm transition ${
                active === s.id
                  ? "border-accent font-medium text-accent"
                  : "border-transparent text-muted hover:border-border hover:text-foreground"
              }`}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
