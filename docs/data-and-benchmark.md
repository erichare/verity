# The open benchmark and data API

Verity publishes a normalized, content-addressed catalog of public forensic surface
scans and three **frozen benchmark splits**, served by a REST data API at
[data.verity.codes](https://data.verity.codes). This is the public face of
[`services/catalog`](../services/catalog); it supersedes the earlier internal catalog
planning notes.

## The catalog

- **Normalized + content-addressed.** Scans are stored under their content hash with
  study / firearm / mark metadata in a relational catalog; ingestion is idempotent.
- **Harvesters:** NBTRD (which has no API of its own — scans are harvested and
  normalized), Figshare, and GitHub repositories
  ([`services/catalog/verity_catalog/harvest/`](../services/catalog/verity_catalog/harvest/)),
  plus multi-instrument "virtual kit" ingest and toolmark ingest.
- **CLI:** `verity-catalog` (`crawl-study`, `info`, `ingest`, `ingest-toolmarks`,
  `ingest-virtual-kits`, `init-db`, `load-benchmark`, `manifests`, `migrate-db`,
  `sync-blobs`); the REST API is `verity-catalog-api`
  ([`/scalar`](https://data.verity.codes/scalar) reference).

## The frozen splits

Committed at [`services/catalog/benchmarks/`](../services/catalog/benchmarks/), one
directory per split (`pairs.csv.gz`, `folds.json`, `marks.csv.gz`, `provenance.json`,
and the Verity baseline submission + metrics). All three share one protocol — repeated
source-disjoint folds, `test_frac = 0.4`, `seed = 0`, 10 folds — and one frozen scorer
config (hash `ea4ddd51…`, in each `provenance.json`).

| Split | Modality | Pairs (KM / KNM) | Sources | Split hash (sha256, prefix) |
|---|---|---|---|---|
| `bullets-v1` | striated bullet lands | 1901 (146 / 1755) | 38 | `7aa24c56…` |
| `cartridge-v1` | impressed breech faces | 190 (10 / 180) | 10 | `31aea8c3…` |
| `toolmark-v1` | striated toolmarks | 167332 (3530 / 163802) | 56 | `4ead8b69…` |

The contract: one likelihood ratio per pair, produced without using the benchmark
labels of any pair involving either of its sources (leave-the-pair's-sources-out) —
the same source-disjoint discipline the frozen folds score. Submissions are ranked by
Cllr (mean over folds); the calibration loss (`Cllr − Cllr_min`) is highlighted
alongside — it cannot be the sort key, because the uninformative LR = 1 submission has
zero calibration loss. Baseline results are in
[`headline-numbers.md`](headline-numbers.md).

## The API surface

Base URL `https://data.verity.codes`:

- `GET /benchmark/splits` — list the frozen splits with hashes and counts.
- `GET /benchmark/splits/{name}` — one split's protocol, counts, and provenance.
- `GET /benchmark/splits/{name}/kit` — a replication-kit zip (pairs, folds,
  provenance, the frozen scorer, and a standalone `evaluate.py` — offline evaluation
  equals the leaderboard scoring) for running your own method against the frozen
  protocol.
- `GET /benchmark/splits/{name}/leaderboard` — scored submissions.
- `POST /benchmark/splits/{name}/submissions` — submit per-pair LRs for scoring.
- `GET /datasets/{name}/snapshot` — export a versioned, SHA-256-pinned dataset
  manifest for offline training consumers. Each row includes its license,
  physical-source hierarchy, content hash, current blob availability, and X3P
  download route; the snapshot hash excludes mutable store availability, so it
  remains stable when a pending blob finishes syncing.

Catalog browsing (studies, firearms, datasets, marks) is served by the same API — see
the interactive reference at
[data.verity.codes/scalar](https://data.verity.codes/scalar).

## Reproducing the Verity baseline

Each split directory commits the Verity baseline submission
(`verity_submission.csv.gz`) and its scored metrics (`verity_metrics.json`);
`verity-build-benchmark` (in [`services/engine`](../services/engine)) regenerates
them from the frozen split and the committed reference. The validation narrative is
in [`validation.md`](validation.md).
