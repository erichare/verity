# Contributing to Verity

Thanks for your interest in improving Verity — an open forensic
surface-comparison platform. This guide covers local development setup for each
package in the monorepo, the conventions pull requests must follow, and the
policy for changes that affect published validation numbers.

If you are reporting a problem rather than sending code, please use the
[issue templates](.github/ISSUE_TEMPLATE/) — including the dedicated
**validation issue** template for challenging any published number.

All participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Repository layout

| Package | Lang / tooling | Role |
|---|---|---|
| [`crates/verity-x3p`](crates/verity-x3p) | Rust (cargo workspace) | Native X3P (ISO 25178-72) codec — single source of truth for the format. |
| [`bindings/python`](bindings/python) | PyO3 + maturin | Python binding (`verity_x3p`) to the Rust core. |
| [`bindings/r/verityx3p`](bindings/r/verityx3p) | extendr | R binding to the Rust core. |
| [`services/engine`](services/engine) | Python (uv) | Metrology preprocessing, registration, CMR, calibrated-LR layer. |
| [`services/api`](services/api) | FastAPI (uv) | The comparison HTTP API (api.verity.codes). |
| [`services/catalog`](services/catalog) | Python (uv) | Data catalog + content-addressed store + REST data API. |
| [`services/mcp`](services/mcp) | Python (uv) | MCP server exposing the comparison API as tools. |
| [`services/web`](services/web) | Next.js (pnpm) | verity.codes / docs.verity.codes / app.verity.codes. |
| [`clients/`](clients) | Python / R | Thin API clients + the content-handle reproducibility contract. |

## Prerequisites

- **Rust** (stable) — required even for the Python services: they depend on
  `bindings/python` (a PyO3 extension) via `[tool.uv.sources]`, so building any
  Python environment compiles Rust.
- **[uv](https://docs.astral.sh/uv/)** — manages every Python environment
  (Python 3.12 recommended; scientific-stack wheels are reliable there).
- **Node 22 + [pnpm](https://pnpm.io) 10** — for `services/web`.
- **R** (optional) — only if you work on the R binding.

## Dev setup per package

Commands below mirror what CI actually runs (see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Please run the
relevant ones locally before opening a PR.

### Rust workspace (`crates/verity-x3p`)

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
```

### Python binding (`bindings/python`)

```bash
cd bindings/python
uv run --with pytest pytest tests    # what CI runs (builds the extension via uv)

# Or, for iterative development inside a venv:
uv venv --python 3.12 && source .venv/bin/activate
uv pip install maturin
maturin develop                       # build + install into the active venv
```

### Engine (`services/engine`)

```bash
cd services/engine
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev pytest
```

### Comparison API (`services/api`)

```bash
cd services/api
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev pytest
uv run --extra dev verity-api        # serve locally on :8000
```

The API test suite fits bootstrap calibration ensembles, which is slow cold.
Two env knobs (also used by CI) make it fast:

```bash
export VERITY_LR_BOOTSTRAP_N=150                    # vs the 1000 production default
export VERITY_ENSEMBLE_CACHE_DIR=~/.cache/verity-ensembles   # persist fitted ensembles
```

### Data catalog (`services/catalog`)

```bash
cd services/catalog
uv sync --extra dev --extra api --extra ingest --extra s3   # the CI extras
uv run --extra dev --extra api --extra ingest --extra s3 ruff check .
uv run --extra dev --extra api --extra ingest --extra s3 pytest
uv run --extra api verity-catalog-api                       # data API on :8001
```

Configuration is env-driven (`VERITY_CATALOG_*`) — see
[`services/catalog/.env.example`](services/catalog/.env.example).

### MCP server (`services/mcp`)

```bash
cd services/mcp
uv sync --extra dev
uv run --extra dev ruff check .
uv run --extra dev pytest
```

### Web (`services/web`)

```bash
cd services/web
pnpm install
pnpm typecheck     # what CI runs
pnpm build
pnpm dev           # local dev server on :3000
```

Client-side configuration is `NEXT_PUBLIC_*` env vars — see
[`services/web/.env.example`](services/web/.env.example). Note that
`NEXT_PUBLIC_*` values are inlined at **build** time.

### R binding (`bindings/r/verityx3p`, optional)

```bash
R CMD INSTALL bindings/r/verityx3p
R CMD check --no-manual bindings/r/verityx3p   # --no-manual unless LaTeX is installed
```

## Pull request conventions

- **Conventional commits**, matching the existing history:
  `feat(web): …`, `fix(api): …`, `docs: …`, `chore: …`, `test(engine): …`,
  `refactor(catalog): …`. The scope is the package you touched.
- **One focused PR per change.** Small, reviewable diffs; don't bundle an
  unrelated refactor with a fix.
- **Tests are required.** New behavior comes with tests; bug fixes come with a
  regression test. CI (Rust fmt/clippy/test, ruff + pytest per Python service,
  web typecheck) must be green before review.
- Don't commit generated artifacts, data dumps, or secrets. `.env` files stay
  local; only `.env.example` files are committed.

## Method-change policy (validation numbers)

Verity's credibility rests on protocol-labeled, reproducible numbers.
[`docs/headline-numbers.md`](docs/headline-numbers.md) is the canonical
registry: every figure quoted anywhere (README, whitepaper, web, slides) must
match a row there or carry the same scope label.

Therefore:

- **Any change that affects a validation number** — preprocessing, registration,
  scoring, calibration, reference bundles, fold/protocol definitions — **must
  update `docs/headline-numbers.md` in the same PR**, and say so explicitly in
  the PR description.
- Keep protocol labels intact. In-sample, source-disjoint, and
  frozen-benchmark figures are different protocols and are never
  interchangeable; never present an in-sample number as a validation claim.
- If a change shifts a published number and the shift is intended, the PR must
  explain why. If it is not intended, that's a regression — fix it, don't
  relabel it.

The PR template asks "does this change any published number?" — answer it
honestly; reviewers will check.

## Questions

Open a [discussion issue](.github/ISSUE_TEMPLATE/) or email
<ericrhare@gmail.com>.
