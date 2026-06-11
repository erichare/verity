"use client";

import { useEffect, useState } from "react";
import { SiteNav } from "@/components/SiteNav";
import {
  catalogConfigured,
  getScans,
  getStudies,
  scanMarkType,
  sourceLabel,
  type MarkClass,
  type Scan,
  type Study,
} from "@/lib/catalog";

const PAGE = 25;

// The mark-class filter chips. "all" shows every scan; the others narrow to a
// surface family so striated (bullet land) and impressed (cartridge) marks are
// distinguishable — the catalog is multi-modal, not bullet-only.
const MARK_FILTERS: { value: MarkClass; label: string }[] = [
  { value: "all", label: "All marks" },
  { value: "bullet", label: "Bullet lands" },
  { value: "cartridge", label: "Cartridge breech faces" },
  { value: "toolmark", label: "Tool marks" },
];

function shortHash(h: string): string {
  return `${h.slice(0, 10)}…${h.slice(-6)}`;
}

export default function CatalogPage() {
  const [studies, setStudies] = useState<Study[]>([]);
  const [scans, setScans] = useState<Scan[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [markClass, setMarkClass] = useState<MarkClass>("all");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getStudies().then(setStudies);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getScans({ search, markClass, limit: PAGE, offset: page * PAGE }).then((r) => {
      if (!active) return;
      setScans(r.scans);
      setTotal(r.total);
      setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [search, markClass, page]);

  const maxPage = Math.max(0, Math.ceil(total / PAGE) - 1);

  return (
    <>
      <SiteNav />
      <main className="mx-auto w-full max-w-6xl px-6 pb-24 pt-28 sm:pt-36">
        <section className="rise max-w-3xl">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Live · read-only · content-hash provenance
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
            The <span className="accent-text">benchmark catalog</span>
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-foreground/80">
            The public benchmark data Verity is validated against &mdash; bullet lands, cartridge
            breech faces, and screwdriver tool marks, normalized into one queryable catalog where
            every scan carries its SHA-256 content hash and a link back to its source. This is a
            live, read-only view of the hosted data.
          </p>
        </section>

        {!catalogConfigured && (
          <p className="mt-10 rounded-xl border border-amber-400/30 bg-amber-400/10 p-4 text-sm text-amber-700 dark:text-amber-200">
            The catalog endpoint isn&rsquo;t configured for this deployment yet
            (<code>NEXT_PUBLIC_SUPABASE_URL</code> / <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code>).
          </p>
        )}

        {studies.length > 0 && (
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {studies.map((s) => (
              <div key={s.id} className="glass rounded-2xl p-5">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-accent">
                    {s.source}
                  </span>
                  {s.consecutively_manufactured && (
                    <span className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted">
                      consecutively manufactured
                    </span>
                  )}
                </div>
                <h2 className="mt-1.5 font-display text-lg font-medium text-foreground">{s.title}</h2>
                <p className="mt-1 truncate font-mono text-xs text-muted" title={s.external_id}>
                  {s.external_id}
                </p>
              </div>
            ))}
          </div>
        )}

        <div className="mt-12">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="font-display text-2xl font-medium text-foreground">Scans</h2>
              <p className="mt-1 text-sm text-muted">
                {loading ? "Loading…" : `${total.toLocaleString()} scans`} · 3-D surface scans (X3P) + 1-D tool-mark profiles
              </p>
            </div>
            <input
              type="search"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(0);
              }}
              placeholder="Filter by filename (e.g. Barrel1, Hamby252)…"
              className="glass w-full max-w-xs rounded-full px-4 py-2 text-sm text-foreground outline-none placeholder:text-muted focus:ring-1 focus:ring-accent/40"
            />
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            {MARK_FILTERS.map((f) => {
              const active = markClass === f.value;
              return (
                <button
                  key={f.value}
                  onClick={() => {
                    setMarkClass(f.value);
                    setPage(0);
                  }}
                  aria-pressed={active}
                  className={`rounded-full px-4 py-1.5 text-xs font-medium transition ${
                    active
                      ? "bg-accent text-background"
                      : "glass text-foreground/70 hover:text-foreground"
                  }`}
                >
                  {f.label}
                </button>
              );
            })}
          </div>

          <div className="mt-5 overflow-x-auto rounded-2xl border border-border">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="border-b border-border bg-foreground/[0.03] text-[11px] uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Filename</th>
                  <th className="px-4 py-3 font-medium">Mark type</th>
                  <th className="px-4 py-3 font-medium">Pitch (µm)</th>
                  <th className="px-4 py-3 font-medium">SHA-256</th>
                  <th className="px-4 py-3 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {scans.map((sc) => (
                  <tr key={sc.id} className="border-b border-border/60 last:border-0">
                    <td className="px-4 py-2.5 text-foreground/90">{sc.filename ?? `scan ${sc.id}`}</td>
                    <td className="px-4 py-2.5 text-muted">{scanMarkType(sc)}</td>
                    <td className="px-4 py-2.5 font-mono text-foreground/70">
                      {sc.lateral_resolution_x != null ? sc.lateral_resolution_x.toFixed(3) : "—"}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="font-mono text-xs text-foreground/60" title={sc.content_hash}>
                        {shortHash(sc.content_hash)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <a
                        href={sc.source_ref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-accent underline decoration-border underline-offset-2 hover:decoration-accent"
                      >
                        {sourceLabel(sc)} ↗
                      </a>
                    </td>
                  </tr>
                ))}
                {!loading && scans.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted">
                      No scans match that filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {total > PAGE && (
            <div className="mt-4 flex items-center justify-between text-sm text-muted">
              <span>
                Page {page + 1} of {maxPage + 1}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="glass rounded-full px-4 py-1.5 text-foreground/80 transition hover:text-foreground disabled:opacity-40"
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(maxPage, p + 1))}
                  disabled={page >= maxPage}
                  className="glass rounded-full px-4 py-1.5 text-foreground/80 transition hover:text-foreground disabled:opacity-40"
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>

        <p className="mt-10 max-w-3xl text-xs leading-relaxed text-muted">
          Mirrored read-only from three open sources: NIST NBTRD scans (U.S. public domain),
          CSAFE-ISU cartridge-case scans (CC BY 4.0), and tmaRks screwdriver toolmarks (MIT).
          Content hashes pin each scan byte-for-byte; the same catalog powers Verity&rsquo;s
          reproducible validation. X3P blob downloads are served separately and are not enabled
          on this public view.
        </p>
      </main>
    </>
  );
}
