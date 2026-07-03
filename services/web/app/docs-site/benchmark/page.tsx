import type { Metadata } from "next";
import { Reveal } from "@/components/Reveal";
import { SplitHash } from "@/components/benchmark/SplitHash";
import {
  benchmarkConfigured,
  getSplits,
  getSubmissions,
  kitUrl,
  modalityLabel,
  submitUrl,
  type BenchmarkSplit,
  type BenchmarkSubmission,
} from "@/lib/benchmark";
import { JsonLd, benchmarkDatasetJsonLd } from "@/components/seo/JsonLd";

const BENCH_TITLE = "Open benchmark — frozen, source-disjoint, replicable";
const BENCH_DESC =
  "A frozen, source-disjoint benchmark for calibrated forensic-comparison likelihood ratios across bullet lands, cartridge breech faces, and toolmarks — with a downloadable replication kit and a leaderboard that scores calibration, not just discrimination.";

export const metadata: Metadata = {
  title: BENCH_TITLE,
  description: BENCH_DESC,
  alternates: { canonical: "/benchmark" },
  openGraph: {
    type: "website",
    siteName: "Verity",
    url: "/benchmark",
    title: BENCH_TITLE,
    description: BENCH_DESC,
    images: [{ url: "/opengraph-image", alt: "Verity — the open benchmark" }],
  },
};

export const revalidate = 300;

function fmt(x: number | null | undefined, digits = 3): string {
  return x == null ? "—" : x.toFixed(digits);
}

function Leaderboard({
  split,
  rows,
}: {
  split: BenchmarkSplit;
  rows: BenchmarkSubmission[];
}) {
  if (rows.length === 0) {
    return (
      <p className="mt-4 text-sm text-foreground/70">
        No scored submissions yet — download the kit below and be the first.
      </p>
    );
  }
  return (
    <>
      {/* Mobile (<md): one card per submission so every metric — including the
          headline calibration loss — is visible without horizontal scrolling. */}
      <ul className="mt-4 space-y-3 md:hidden">
        {rows.map((s, i) => (
          <li
            key={`${s.submitter}-${s.created_at}-card`}
            className={`rounded-xl border p-4 ${
              s.is_reference ? "border-accent/30 bg-accent/5" : "border-border"
            }`}
          >
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-sm text-muted">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium">
                    {s.url ? (
                      <a
                        href={s.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:accent-text underline-offset-4 hover:underline"
                      >
                        {s.method}
                      </a>
                    ) : (
                      s.method
                    )}
                  </span>
                  {s.is_reference && (
                    <span className="rounded-full border border-accent/30 px-2 py-0.5 text-[10px] uppercase tracking-wider accent-text">
                      reference
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted">{s.submitter}</div>
              </div>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-border/50 pt-3">
              <div>
                <dt className="text-xs text-muted">Calibration loss</dt>
                <dd className="font-mono text-sm font-semibold accent-text">
                  {s.calibration_loss >= 0 ? "+" : ""}
                  {fmt(s.calibration_loss)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Cllr</dt>
                <dd className="font-mono text-sm">
                  {fmt(s.cllr)}
                  <span className="text-muted"> ±{fmt(s.cllr_std, 2)}</span>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Cllr_min</dt>
                <dd className="font-mono text-sm text-foreground/70">{fmt(s.cllr_min)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">AUC</dt>
                <dd className="font-mono text-sm text-foreground/70">{fmt(s.auc)}</dd>
              </div>
            </dl>
            <div className="mt-2 text-xs text-muted">
              {new Date(s.created_at).toISOString().slice(0, 10)}
            </div>
          </li>
        ))}
      </ul>

      {/* md+: the full leaderboard table (640px fits without horizontal scroll). */}
      <div className="mt-4 hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] border-collapse text-left">
        <caption className="sr-only">
          Leaderboard for {split.title} — submissions ranked by total Cllr
        </caption>
        <thead>
          <tr className="border-b border-border text-xs uppercase tracking-wider text-muted">
            <th scope="col" className="px-2 py-2 sm:px-3">#</th>
            <th scope="col" className="px-2 py-2 sm:px-3">Method</th>
            <th scope="col" className="px-2 py-2 text-center sm:px-3">
              Cllr <span className="normal-case text-muted">(rank)</span>
            </th>
            <th scope="col" className="px-2 py-2 text-center sm:px-3">Cllr_min</th>
            <th scope="col" className="px-2 py-2 text-center accent-text sm:px-3">Calibration loss</th>
            <th scope="col" className="px-2 py-2 text-center sm:px-3">AUC</th>
            <th scope="col" className="px-2 py-2 text-right sm:px-3">Date</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s, i) => (
            <tr
              key={`${s.submitter}-${s.created_at}`}
              className={`border-b border-border/50 ${s.is_reference ? "bg-accent/5" : ""}`}
            >
              <td className="px-2 py-2.5 font-mono text-sm text-muted sm:px-3">{i + 1}</td>
              <td className="px-2 py-2.5 sm:px-3">
                <div className="text-sm font-medium">
                  {s.url ? (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:accent-text underline-offset-4 hover:underline"
                    >
                      {s.method}
                    </a>
                  ) : (
                    s.method
                  )}
                  {s.is_reference && (
                    <span className="ml-2 rounded-full border border-accent/30 px-2 py-0.5 text-[10px] uppercase tracking-wider accent-text">
                      reference
                    </span>
                  )}
                </div>
                <div className="text-xs text-muted">{s.submitter}</div>
              </td>
              <td className="px-2 py-2.5 text-center font-mono text-sm sm:px-3">
                {fmt(s.cllr)}
                <span className="text-muted"> ±{fmt(s.cllr_std, 2)}</span>
              </td>
              <td className="px-2 py-2.5 text-center font-mono text-sm text-foreground/70 sm:px-3">
                {fmt(s.cllr_min)}
              </td>
              <td className="px-2 py-2.5 text-center font-mono text-sm font-semibold accent-text sm:px-3">
                {s.calibration_loss >= 0 ? "+" : ""}
                {fmt(s.calibration_loss)}
              </td>
              <td className="px-2 py-2.5 text-center font-mono text-sm text-foreground/70 sm:px-3">
                {fmt(s.auc)}
              </td>
              <td className="px-2 py-2.5 text-right text-xs text-muted sm:px-3">
                {new Date(s.created_at).toISOString().slice(0, 10)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </>
  );
}

function SplitCard({
  split,
  rows,
}: {
  split: BenchmarkSplit;
  rows: BenchmarkSubmission[];
}) {
  const curl = `curl -X POST ${submitUrl(split)} \\
  -H 'Content-Type: application/json' \\
  -d '{"submitter": "you", "method": "your-method", "url": "https://…",
       "csv": "pair_id,lr\\n<one LR per frozen pair>"}'`;
  return (
    <Reveal>
      <section className="rounded-2xl border border-border bg-card/60 p-6 sm:p-8">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xl font-semibold">{split.title}</h2>
          <span className="rounded-full border border-border px-3 py-1 text-xs text-foreground/70">
            {modalityLabel(split.modality)}
          </span>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-5">
          <div>
            <dt className="text-muted">Pairs</dt>
            <dd className="font-mono">{split.n_pairs.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-muted">Same-source</dt>
            <dd className="font-mono">{split.n_km.toLocaleString()}</dd>
          </div>
          <div>
            <dt className="text-muted">Sources</dt>
            <dd className="font-mono">{split.n_sources}</dd>
          </div>
          <div>
            <dt className="text-muted">Frozen folds</dt>
            <dd className="font-mono">{split.n_folds}</dd>
          </div>
          <div>
            <dt className="text-muted">Split hash</dt>
            <dd className="font-mono">
              <SplitHash hash={split.split_hash} />
            </dd>
          </div>
        </dl>

        <Leaderboard split={split} rows={rows} />

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <a
            href={kitUrl(split)}
            className="rounded-lg border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-medium accent-text transition hover:bg-accent/20"
          >
            Download replication kit ↓
          </a>
          <details className="group">
            <summary className="cursor-pointer text-sm text-foreground/70 transition hover:text-foreground">
              Submit your method
            </summary>
            <pre className="mt-3 overflow-x-auto rounded-lg border border-border bg-background/60 p-4 text-xs leading-relaxed text-foreground/80">
              {curl}
            </pre>
            <p className="mt-2 max-w-2xl text-xs text-muted">
              One finite, positive likelihood ratio per frozen pair. The kit&apos;s{" "}
              <code className="font-mono">evaluate.py</code> scores your submission offline with
              the identical code — what you see locally is what the leaderboard records.
            </p>
          </details>
        </div>
      </section>
    </Reveal>
  );
}

export default async function BenchmarkPage() {
  const [splits, submissions] = await Promise.all([getSplits(), getSubmissions()]);
  const bySplit = new Map<number, BenchmarkSubmission[]>();
  for (const s of submissions) {
    const list = bySplit.get(s.split_id) ?? [];
    list.push(s);
    bySplit.set(s.split_id, list);
  }

  return (
    <main id="main" className="mx-auto w-full min-w-0 max-w-5xl px-4 pb-24 pt-28 sm:px-6">
      <JsonLd data={benchmarkDatasetJsonLd} />

      <Reveal>
        <p className="text-xs font-medium uppercase tracking-[0.2em] accent-text">
          Open benchmark
        </p>
        <h1 className="mt-3 max-w-3xl text-3xl font-semibold leading-tight sm:text-4xl">
          Frozen pairs. Source-disjoint folds. Calibration on the scoreboard.
        </h1>
        <p className="mt-4 max-w-3xl text-foreground/70">
          Most published comparison algorithms report discrimination (AUC, error rates) on
          splits of their own choosing. This benchmark freezes the comparison pairs and the
          source-disjoint evaluation folds — committed to by a cryptographic split hash — and
          scores what the field does not otherwise measure:{" "}
          <strong className="text-foreground">
            how honest the reported likelihood ratios are
          </strong>{" "}
          (calibration loss, Cllr − Cllr_min), alongside total Cllr and AUC.
        </p>
      </Reveal>

      <Reveal>
        <div className="mt-8 grid gap-4 sm:grid-cols-3">
          {[
            {
              t: "Frozen + content-addressed",
              d: "Every pair is identified by the SHA-256 hashes of its marks; the split hash commits to pairs, labels, and folds. Hash equality means same benchmark — no silent re-splitting.",
            },
            {
              t: "Source-disjoint by construction",
              d: "A fold's test pairs involve only held-out barrels, slides, or tool edges. The contract: calibrate each pair's LR without using labels from either of its sources.",
            },
            {
              t: "Replicable offline",
              d: "The kit ships the frozen pairs, folds, provenance, the scorer, and a standalone evaluate.py whose output equals the leaderboard scoring exactly.",
            },
          ].map((c) => (
            <div key={c.t} className="rounded-xl border border-border bg-card/40 p-5">
              <h2 className="text-sm font-semibold">{c.t}</h2>
              <p className="mt-2 text-sm leading-relaxed text-foreground/70">{c.d}</p>
            </div>
          ))}
        </div>
      </Reveal>

      <div className="mt-12 space-y-8">
        {splits.length === 0 ? (
          <Reveal>
            <div className="rounded-2xl border border-border bg-card/40 p-8 text-center text-foreground/70">
              {benchmarkConfigured
                ? "The frozen splits are being published — check back shortly."
                : "Benchmark data is not configured for this deployment."}
            </div>
          </Reveal>
        ) : (
          splits.map((split) => (
            <SplitCard key={split.id} split={split} rows={bySplit.get(split.id) ?? []} />
          ))
        )}
      </div>

      <Reveal>
        <p className="mt-12 max-w-3xl text-sm leading-relaxed text-muted">
          The ground-truth labels are public (the underlying scans are open data), so this is a
          replication benchmark, not a blind contest: the leaderboard ranks by total Cllr — the
          proper scoring rule — and the submission contract asks for source-disjoint
          calibration, the same discipline Verity&apos;s own reference rows follow. Verity&apos;s
          baselines are leave-the-pair&apos;s-sources-out calibrated and reproducible from the
          public catalog with{" "}
          <code className="font-mono text-foreground/70">verity-build-benchmark</code>.
        </p>
        <p className="mt-4 max-w-3xl text-sm leading-relaxed text-foreground/50">
          Everything this page reads — the frozen splits, the leaderboard, and the replication
          kits — is served by the open Data API at{" "}
          <a
            href="https://data.verity.codes/scalar"
            target="_blank"
            rel="noopener noreferrer"
            className="text-foreground/70 underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
          >
            data.verity.codes ↗
          </a>
          .
        </p>
      </Reveal>
    </main>
  );
}
