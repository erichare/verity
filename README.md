<div align="center">

# Verity

**An open, domain-general engine for forensic surface comparison — a transparent, calibrated _likelihood ratio_, not a black-box "match."**

[![CI](https://github.com/erichare/verity/actions/workflows/ci.yml/badge.svg)](https://github.com/erichare/verity/actions/workflows/ci.yml)
[![crates.io](https://img.shields.io/crates/v/verity-x3p.svg?label=crates.io)](https://crates.io/crates/verity-x3p)
[![PyPI](https://img.shields.io/pypi/v/verity-x3p.svg?label=PyPI)](https://pypi.org/project/verity-x3p/)
[![License: MIT/Apache-2.0](https://img.shields.io/badge/license-MIT%20%2F%20Apache--2.0-blue.svg)](#license)
[![Status: early](https://img.shields.io/badge/status-early%20%2F%20active-f59e0b.svg)](#status--roadmap)

[**Live app**](https://verity.codes) · [**Studio**](https://app.verity.codes) · [Method docs](https://docs.verity.codes/method) · [Open benchmark](https://data.verity.codes) · [Docs](https://docs.verity.codes) · [API reference](https://api.verity.codes/scalar)

<img src="docs/assets/home-hero.svg" alt="Verity — forensic marks, weighed as evidence" width="720">

[Why](#why) · [What you get](#what-you-get--a-comparisonreport-not-a-verdict) · [Validation](#validation-honest) · [How it works](#how-it-works) · [Quickstart](#quickstart) · [Repo map](#repository-map) · [Roadmap](#status--roadmap) · [License](#license)

</div>

---

Verity compares 3-D surface-topography scans — bullet lands, cartridge-case breech-face impressions, striated and impressed toolmarks, and (in time) footwear and fractured surfaces — directly from [X3P](https://www.iso.org/standard/62395.html) files (ISO 25178-72). It pairs a domain-general surface comparison with a **transparent, calibrated likelihood-ratio decision layer** and region-level attribution. The machine never reports a "match"; it reports an *auditable weight of evidence*, characterized on a named dataset.

> [!NOTE]
> **Status: early.** The X3P codec (`verity-x3p`, v0.2.0) is published on crates.io and PyPI and tested against real-world files. The engine, comparison API, and web app are live; the first-principles method is validated source-disjoint across bullet lands, cartridge cases, and toolmarks (see [Validation](#validation-honest)). The full firearms-proof validation is in progress. The next external test is pre-registered on [OSF](https://osf.io/prjs9) (filed 2026-07-01) — frozen protocol, win or lose: [`docs/weller-preregistration.md`](docs/weller-preregistration.md) (result pending).

```bash
cargo add verity-x3p                    # crates.io, v0.2.0
pip install verity-x3p                  # PyPI, abi3 wheels, Python 3.9+
R CMD INSTALL bindings/r/verityx3p      # from a clone of this repo; not on CRAN; requires a Rust toolchain
```

Full quickstart [below](#quickstart) · [codec changelog](CHANGELOG.md)

## Why

Forensic firearm/toolmark comparison today is either subjective examiner judgment or proprietary black-box correlation (IBIS), while the open tooling is a pile of *domain-specific* R packages with no unified, deployable platform. Courts are increasingly skeptical of unqualified pattern-match testimony (*Abruquah v. Maryland*, 2023; the 2023 amendment to FRE 702), and **no discipline yet has a well-characterized error rate** (Cuellar et al., 2024). Verity's bet: **one general, calibrated, explainable method** — proven first where ground truth is strongest (firearms), then transferred across domains. More: [docs.verity.codes/why](https://docs.verity.codes/why).

## What you get — a `ComparisonReport`, not a verdict

A likelihood ratio with its verbal equivalent and a **credible interval** (a clustered bootstrap of the reference, so the LR carries its own calibration uncertainty), a characterized cost (**Cllr**) on a *named* reference population, an **empirical cap** (ELUB-inspired) on how strong a claim the data can support, and the **region-level attribution** that drove the score.

```jsonc
{
  "likelihood_ratio": 146.0,
  "log10_lr": 2.16,
  "verbal": "moderately strong support for same source",
  "lr_bound_log10": 2.16,
  // a percentile credible interval on log10 LR — the reference is bootstrapped
  // (clustered by source/barrel) and refit
  "log10_lr_ci_lo": 1.74, "log10_lr_ci_hi": 2.16, "lr_ci_method": "bootstrap-clustered",
  // reference diagnostics are the *in-sample* fit of the named reference; the honest
  // validation figure is the source-disjoint Cllr ≈ 0.19 pooled (≈ 0.11 on Hamby-252
  // alone) — every number, with its protocol, lives in docs/headline-numbers.md
  "reference": { "name": "pooled bullet-land reference (Hamby-252 & 173, Beretta, Phoenix)",
                 "n_km": 146, "n_knm": 1755,
                 "auc": 0.984, "cllr": 0.193, "cllr_min": 0.168 },
  "attribution": [ /* the matched regions — the explanation */ ],
  "scope_note": "This is a calibrated weight of evidence on the pooled bullet-land reference population. It is not a verdict: it is one input to an examiner's judgment, alongside case context. It is not a claim about the error rate of striated examination, which remains unknown."
}
```

## Validation (honest)

> [!IMPORTANT]
> Every number below carries its exact protocol — in-sample vs. source-disjoint vs. the frozen open-benchmark protocol are different claims and are never mixed. The canonical registry is [`docs/headline-numbers.md`](docs/headline-numbers.md) — every figure here matches a row there, and that protocol-labeled table is the citable source.

**One method, three mark families** — one algorithm (CMR), one frozen scorer config, validated source-disjoint in each family on the frozen open benchmark (fold mean):

| Mark family | Frozen split | Cllr | AUC |
|---|---|---|---|
| Bullet lands (striated) | `bullets-v1` | 0.205 ± 0.125 | 0.979 |
| Cartridge breech faces (impressed) | `cartridge-v1` | 0.398 ± 0.202[^cart] | 0.922 |
| Screwdriver toolmarks (striated) | `toolmark-v1` | 0.330 ± 0.047 | 0.944 |

These characterize **weight of evidence on the named references**, not field error rates.

**Bullet lands, protocol by protocol** — the production scorer is `diag_contrast`, first-principles (no learned representation)[^protocol]; the four studies are Hamby-252/173, PGPD Beretta, and Phoenix Ruger:

| Protocol | Cllr | AUC |
|---|---|---|
| In-sample (deployed reference — optimistic by construction, not a validation claim) | 0.193 (Cllr_min 0.168) | 0.984 |
| Source-disjoint, pooled four studies | 0.186 ± 0.126 | 0.989 |
| Frozen open benchmark `bullets-v1` (fold mean) | 0.205 ± 0.125 | 0.979 |
| Hamby-252 alone, barrel-disjoint[^h252] | 0.113 ± 0.066 | 1.000 |
| Specialist `bulletxtrctr` (random forest), identical protocol, Hamby-252 | 0.064 ± 0.015 | ≈ 1.000 |

An informative, calibrated weight of evidence **from metrology alone**[^cllr]. The trained `bulletxtrctr` random-forest specialist, run through the identical protocol, reaches **Cllr ≈ 0.06 on Hamby-252** — the specialist still leads on its home turf; Verity's contribution on bullets is the calibrated, bounded, deployable LR layer, not a better matcher.

> `diag_contrast` was selected over the Phase-1 `diag_mean` and a multivariate fusion by an explicit barrel-disjoint ablation (`verity-margin`) — candidly, that ablation reused the same four studies as this validation, so a one-shot confirmation on untouched data is the next milestone (see the whitepaper's Limitations). That confirmation is now [pre-registered](docs/weller-preregistration.md) ([OSF, filed 2026-07-01](https://osf.io/prjs9); frozen protocol, published win or lose; result pending).

### What doesn't work yet

The Phase-2b learned representation, trained barrel-disjoint on 210 Hamby scans, **does not beat the cross-correlation baseline** — it overfits (held-out AUC collapses to ≈ 0.67). Synthetic tests confirm the pipeline *does* learn given enough signal: a **data limit, not a defect**. Next: expand the dataset and retest. (Sources: [`services/engine`](services/engine/README.md); the whitepaper's Limitations.)

`verity-validation-report` regenerates the full characterization — Tippett, DET, calibration, and the source-disjoint summary — as a court-ready PDF. The frozen splits, replication kits, and leaderboard live at [data.verity.codes](https://data.verity.codes). Deep dive: [`docs/validation.md`](docs/validation.md) · [whitepaper PDF](docs/whitepaper/verity-whitepaper.pdf).

> [!IMPORTANT]
> Nothing here is a claim about the error rate of forensic examination, which remains unknown.

## How it works

One codec, one truth: `X3P (ISO 25178-72) → verity-x3p (Rust core) → PyO3 / extendr bindings → engine: preprocess (ISO 16610) → register → CMR → calibrate (empirical cap) → ComparisonReport → API · web · MCP`.

- **Statistics decide, not a black box.** A representation produces a *score*; a transparent, empirically-capped calibration turns it into a reportable LR, interpretable *regardless of how the score was computed* — the firewall against the black box.
- **Reproducible by construction.** Deterministic, version-pinned, content-hashed.
- **Open and language-independent.** Built on the X3P standard; MIT/Apache-2.0.

**Congruent Matching Regions (CMR)** generalizes Song's **Congruent Matching Cells** (the standard cartridge-case method) from 2-D cells and a fixed translation+rotation to **regions of any dimension** under **any transformation group** — so one algorithm scores striated, impressed, and (research) fractured marks. Partition a mark into regions, register each against the other mark, and count the regions that agree on one common geometry. The congruent regions *are* the attribution map.

| Modality   | Region              | Transform group           | Reduces to        |
|------------|---------------------|---------------------------|-------------------|
| Striated   | 1-D profile window  | 1-D translation           | ≈ Chumbley / CMS  |
| Impressed  | 2-D grid cell       | 2-D translation+rotation  | ≈ CMC             |
| Fractured  | 3-D mesh patch      | 3-D rigid pose            | (research)        |

Full write-up: [`docs/congruent-matching-regions.md`](docs/congruent-matching-regions.md).

## Quickstart

```python
import verity_x3p
s = verity_x3p.read_x3p("scan.x3p")            # s.data, s.mask are (ny, nx) NumPy arrays
verity_x3p.write_x3p(s, "copy.x3p", z_type="D")
```

<details>
<summary>Rust and R — same core, same bits</summary>

```rust
use verity_x3p::{read_x3p, write_x3p, WriteOptions};
let surface = read_x3p("scan.x3p")?;          // verifies the stored MD5
write_x3p(&surface, "copy.x3p", &WriteOptions::default())?;
```

```r
library(verityx3p)
s <- read_x3p("scan.x3p")                      # s$surface is an nx-by-ny matrix
write_x3p(s, "copy.x3p")
```

</details>

A file written from any binding reads back **bit-identically** in every other.

**Compare two marks over HTTP:**

```bash
curl -s -X POST https://api.verity.codes/compare \
  -F domain=striated \
  -F mark_a=@bulletA_land1.x3p -F mark_a=@bulletA_land2.x3p \
  -F mark_b=@bulletB_land1.x3p -F mark_b=@bulletB_land2.x3p
```

Full docs: [docs.verity.codes](https://docs.verity.codes) · interactive [API reference](https://api.verity.codes/scalar).

**MCP:**

- Hosted remote server at `https://api.verity.codes/mcp` (base64 scan inputs).
- Local stdio via `uv run --directory services/mcp verity-mcp` (env `VERITY_API_URL`); Claude Desktop bundle via `services/mcp/build_mcpb.sh`.
- Six tools (`compare_marks`, `detect_mark_type`, `calibrate_score`, `list_references`, `scorer_config`, `service_health`) — same firewall and scope-note guarantees as the HTTP API.

**Thin clients:** [`clients/python/verity_client.py`](clients/python/verity_client.py) (requests-only) and [`clients/r/verity.R`](clients/r/verity.R); every report carries a `sha256:` content handle over the canonical recipe — `v.reproduce(...)` re-runs and hash-checks it. See [`clients/README.md`](clients/README.md).

<details>
<summary>Develop</summary>

```bash
cargo test -p verity-x3p                        # the Rust core

cd services/engine && uv sync --extra dev && uv run --extra dev pytest
cd services/api    && uv sync --extra dev && uv run --extra dev verity-api   # API on :8000
cd services/web    && pnpm install && pnpm dev                               # web on :3000
```

Full per-package setup, PR conventions, and **the method-change policy** (any PR touching a validation number must update `docs/headline-numbers.md`) live in [`CONTRIBUTING.md`](CONTRIBUTING.md); deployment in [`DEPLOY.md`](DEPLOY.md).

</details>

## Repository map

A polyglot monorepo: one Rust codec core, thin language bindings, and the Python science + service stack on top.

| Package | Lang | Role |
|---|---|---|
| [`crates/verity-x3p`](crates/verity-x3p) | Rust | Native X3P (ISO 25178-72) reader/writer — the format's single source of truth. |
| [`bindings/python`](bindings/python) | PyO3 + NumPy | Python binding to the core (bit-identical I/O). |
| [`bindings/r/verityx3p`](bindings/r/verityx3p) | extendr | R binding to the core (`x3ptools`-compatible layout). |
| [`services/engine`](services/engine) | Python | Metrology preprocessing, registration, CMR, the calibrated-LR decision layer. |
| [`services/api`](services/api) | FastAPI | The comparison HTTP API serving the `ComparisonReport`. |
| [`services/catalog`](services/catalog) | Python | Normalized catalog + content-addressed store + ingestion (NBTRD / Figshare / GitHub harvests, virtual kits). |
| [`services/web`](services/web) | Next.js | [verity.codes](https://verity.codes), [docs.verity.codes](https://docs.verity.codes), and the [Studio](https://app.verity.codes). |
| [`services/mcp`](services/mcp) | Python | MCP server ("verity") — local stdio, plus the hosted endpoint at api.verity.codes/mcp. |
| [`clients/`](clients) | Python / R | Thin API clients + the content-handle reproducibility contract. |

## Status & roadmap

**Done:** `verity-x3p` native codec + Python/R bindings (bit-identical round-trip), v0.2.0 on crates.io and PyPI. Engine: ISO 16610 preprocessing, registration, the calibrated-LR decision layer, CMR; source-disjoint validation across bullet lands, cartridge cases, and toolmarks (tables above). Platform: comparison API, web app, docs, Studio, and the open benchmark — live at verity.codes and api/docs/app/data.verity.codes.

**In progress:** the pre-registered one-shot external validation on untouched data (see [Validation](#validation-honest)).

**Next:** expand the bullet/cartridge/toolmark datasets (NBTRD harvest) and retest the learned representation; CMR-2D → CMC parity on Fadul — `cmcR` still leads, parity is open roadmap; TypeScript/Swift/Java codec bindings. Extending to more mark families: [`docs/toolmark-roadmap.md`](docs/toolmark-roadmap.md).

## Citing & further reading

- **Whitepaper:** [`docs/whitepaper/verity-whitepaper.pdf`](docs/whitepaper/verity-whitepaper.pdf) — full method, validation, and limitations.
- **Validation narrative:** [`docs/validation.md`](docs/validation.md) · **number registry:** [`docs/headline-numbers.md`](docs/headline-numbers.md).
- **Method:** [`docs/congruent-matching-regions.md`](docs/congruent-matching-regions.md) · **open benchmark & data API:** [`docs/data-and-benchmark.md`](docs/data-and-benchmark.md).
- **Cite this repository:** [`CITATION.cff`](CITATION.cff) (GitHub's "Cite this repository" button).
- Community: [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## License

Dual-licensed under either of [**MIT**](LICENSE-MIT) or [**Apache-2.0**](LICENSE-APACHE), at your option. Bundled reference data carries its own upstream attribution — see [`services/api/verity_api/references/NOTICE.md`](services/api/verity_api/references/NOTICE.md).

[^protocol]: Barrel-disjoint: no barrel in both train and test; reported per study, never pooled across makes. First-principles: no learned representation.
[^h252]: Hamby-252 alone — the single strongest study, not the pooled figure; the pooled source-disjoint Cllr is ≈ 0.19 and the frozen `bullets-v1` benchmark reproduces ≈ 0.21.
[^cllr]: `Cllr < 1` = informative; the `Cllr − Cllr_min` gap is the calibration loss the source-disjoint split exposes — answering the Cuellar et al. critique on its own terms.
[^cart]: With only 10 same-source Fadul pairs, per-fold AUC is unstable across protocols (a small-n artifact, not a contradiction — see [`docs/headline-numbers.md`](docs/headline-numbers.md)). The specialist `cmcR` still leads on Fadul; CMR-2D → CMC parity is open roadmap.
