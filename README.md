<div align="center">

# Verity

**An open, domain-general engine for forensic surface comparison — a transparent, calibrated _likelihood ratio_, not a black-box "match."**

[![License: MIT/Apache-2.0](https://img.shields.io/badge/license-MIT%20%2F%20Apache--2.0-blue.svg)](#license)
[![Live: verity.codes](https://img.shields.io/badge/live-verity.codes-22d3ee.svg)](https://verity.codes)
[![API](https://img.shields.io/badge/API-reference-818cf8.svg)](https://api.verity.codes/scalar)
[![Status: early](https://img.shields.io/badge/status-early%20%2F%20active-f59e0b.svg)](#status--roadmap)
![Rust](https://img.shields.io/badge/Rust-core-000000.svg?logo=rust)
![Python](https://img.shields.io/badge/Python-engine-3776AB.svg?logo=python&logoColor=white)
![R](https://img.shields.io/badge/R-binding-276DC3.svg?logo=r&logoColor=white)

[**Live app**](https://verity.codes) · [How it works](https://verity.codes/method) · [Why](https://verity.codes/why) · [Docs](https://verity.codes/docs) · [API reference](https://api.verity.codes/scalar)

![Verity — forensic marks, weighed as evidence](docs/assets/home-hero.svg)

</div>

---

Verity compares 3-D surface-topography scans — bullet lands, cartridge-case
breech-face impressions, striated and impressed toolmarks, and (in time) footwear
and fractured surfaces — directly from [X3P](https://www.iso.org/standard/62395.html)
files (ISO 25178-72). It pairs a domain-general surface comparison with a
**transparent, calibrated likelihood-ratio decision layer** and region-level
attribution. The machine never reports a "match"; it reports an *auditable weight
of evidence*, characterized on a named dataset.

> **Status: early.** The X3P codec (`verity-x3p`) is landed and tested against
> real-world files; the engine, comparison API, and web app are live; the
> first-principles method is validated source-disjoint on Hamby-252 (see
> [Validation](#validation-honest)). The full firearms-proof validation is in
> progress.

## Why

Forensic firearm/toolmark comparison today is either subjective examiner judgment
or proprietary black-box correlation (IBIS), while the open tooling is a pile of
*domain-specific* R packages with no unified, deployable platform. Courts are
increasingly skeptical of unqualified pattern-match testimony (*Abruquah v.
Maryland*, 2023; the 2023 amendment to FRE 702), and **no discipline yet has a
well-characterized error rate** (Cuellar et al., 2024). Verity's bet: **one
general, calibrated, explainable method** — proven first where ground truth is
strongest (firearms), then transferred across domains.

**Design principles**

- **Statistics decide, not a black box.** A representation produces a *score*; a
  transparent, empirically-capped calibration turns that score into a reportable
  likelihood ratio. The report is interpretable *regardless of how the score was
  computed* — the firewall against the black box.
- **Reproducible by construction.** Deterministic, version-pinned, content-hashed.
- **Open and language-independent.** Built on the X3P standard; MIT/Apache-2.0.

## What you get

Not a verdict — a calibrated **`ComparisonReport`**: a likelihood ratio with its
verbal equivalent, a characterized cost (**Cllr**) on a *named* reference
population, an **empirical cap** (ELUB-inspired) on how strong a claim the data
can support, and the **region-level attribution** that drove the score.

```jsonc
{
  "likelihood_ratio": 146.0,
  "verbal": "moderately strong support for same source",
  "lr_bound_log10": 2.16,
  "reference": { "name": "pooled bullet-land", "n_km": 146, "n_knm": 1755, "auc": 0.984, "cllr": 0.193 },
  "attribution": [ /* the matched regions — the explanation */ ],
  "scope_note": "Not a claim about the error rate of examination, which remains unknown."
}
```

## The method — Congruent Matching Regions (CMR)

CMR generalizes Song's **Congruent Matching Cells** (the standard cartridge-case
method) from 2-D cells and a fixed translation+rotation to **regions of any
dimension** under **any transformation group** — so one algorithm scores striated,
impressed, and (research) fractured marks. Partition a mark into regions, register
each against the other mark, and count the regions that agree on one common
geometry. The congruent regions *are* the attribution map.

| Modality   | Region              | Transform group           | Reduces to        |
|------------|---------------------|---------------------------|-------------------|
| Striated   | 1-D profile window  | 1-D translation           | ≈ Chumbley / CMS  |
| Impressed  | 2-D grid cell       | 2-D translation+rotation  | ≈ CMC             |
| Fractured  | 3-D mesh patch      | 3-D rigid pose            | (research)        |

Full write-up: [`docs/congruent-matching-regions.md`](docs/congruent-matching-regions.md).

## Validation (honest)

- **Source-disjoint, first-principles (no learned representation).** Under a
  barrel-disjoint protocol (no barrel in both train and test; reported per study,
  never pooled across makes), the production `diag_contrast` scorer yields on
  held-out barrels **AUC ≈ 1.00 and test Cllr ≈ 0.11 on Hamby-252**, and across
  the four NBTRD bullet studies (Hamby-252/173, PGPD Beretta, Phoenix Ruger)
  **test Cllr ≈ 0.11–0.35 at AUC ≈ 0.97–1.00** — an informative, calibrated
  weight of evidence from metrology alone. (`Cllr < 1` = informative; the
  `Cllr − Cllr_min` gap is the calibration loss the source-disjoint split exposes,
  answering the Cuellar et al. critique on its own terms.) The scorer was selected
  over the Phase-1 `diag_mean` and a multivariate fusion by an explicit
  barrel-disjoint ablation (`verity-margin`) — candidly, that ablation reused the
  same four studies as this validation, so a one-shot confirmation on untouched
  data is the next milestone (see the whitepaper's Limitations); `verity-validation-report`
  regenerates the full characterization — Tippett, DET, calibration, and the
  source-disjoint summary — as a court-ready PDF.
- **Learned representation (Phase-2b).** Trained barrel-disjoint on 210 Hamby
  scans, it **does not beat the cross-correlation baseline** — it overfits
  (held-out AUC collapses to ≈ 0.67). Synthetic tests confirm the pipeline *does* learn
  given enough signal: a **data limit, not a defect**. Next: expand the dataset
  and retest.

Nothing here is a claim about the error rate of forensic examination, which
remains unknown.

## Repository map

A polyglot monorepo: one Rust codec core, thin language bindings, and the Python
science + service stack on top.

| Package | Lang | Role |
|---|---|---|
| [`crates/verity-x3p`](crates/verity-x3p) | Rust | Native X3P (ISO 25178-72) reader/writer — the format's single source of truth. |
| [`bindings/python`](bindings/python) | PyO3 + NumPy | Python binding to the core (bit-identical I/O). |
| [`bindings/r/verityx3p`](bindings/r/verityx3p) | extendr | R binding to the core (`x3ptools`-compatible layout). |
| [`services/engine`](services/engine) | Python | Metrology preprocessing, registration, CMR, the calibrated-LR decision layer. |
| [`services/api`](services/api) | FastAPI | The comparison HTTP API serving the `ComparisonReport`. |
| [`services/catalog`](services/catalog) | Python | Normalized catalog + content-addressed store + ingestion (NBTRD/Figshare). |
| [`services/web`](services/web) | Next.js | [verity.codes](https://verity.codes) and the interactive comparison UI. |

## Quickstart

### The X3P codec — Rust / Python / R

```rust
use verity_x3p::{read_x3p, write_x3p, WriteOptions};
let surface = read_x3p("scan.x3p")?;          // verifies the stored MD5
write_x3p(&surface, "copy.x3p", &WriteOptions::default())?;
```

```python
import verity_x3p
s = verity_x3p.read_x3p("scan.x3p")            # s.data, s.mask are (ny, nx) NumPy arrays
verity_x3p.write_x3p(s, "copy.x3p", z_type="D")
```

```r
library(verityx3p)
s <- read_x3p("scan.x3p")                      # s$surface is an nx-by-ny matrix
write_x3p(s, "copy.x3p")
```

A file written from any binding reads back **bit-identically** in every other.

### Compare two marks over HTTP

```bash
curl -s -X POST https://api.verity.codes/compare \
  -F domain=striated \
  -F mark_a=@bulletA_land1.x3p -F mark_a=@bulletA_land2.x3p \
  -F mark_b=@bulletB_land1.x3p -F mark_b=@bulletB_land2.x3p
```

See the full **[docs](https://verity.codes/docs)** and the interactive
**[API reference](https://api.verity.codes/scalar)**.

### Develop

```bash
cargo test -p verity-x3p                        # the Rust core

cd services/engine && uv venv --python 3.12 && uv pip install -e ".[dev]" && uv run pytest
cd services/api    && uv run --extra dev verity-api          # API on :8000
cd services/web    && pnpm install && pnpm dev               # web on :3000
```

Deployment (Vercel + a container host for the API) is documented in
[`DEPLOY.md`](DEPLOY.md).

## Status & roadmap

- ✅ **`verity-x3p`** native codec + Python/R bindings (bit-identical round-trip).
- ✅ **Engine**: ISO 16610 preprocessing, registration, the calibrated-LR decision
  layer, CMR; source-disjoint Hamby validation.
- ✅ **Platform**: comparison API + web app, live at verity.codes.
- 🔜 Expand the bullet/cartridge/toolmark datasets (NBTRD harvest) and retest the
  learned representation; CMR-2D → CMC parity on Fadul; TypeScript/Swift/Java
  codec bindings.

## License

Dual-licensed under either of [**MIT**](LICENSE-MIT) or
[**Apache-2.0**](LICENSE-APACHE), at your option. Bundled reference data carries
its own upstream attribution — see
[`services/api/verity_api/references/NOTICE.md`](services/api/verity_api/references/NOTICE.md).
