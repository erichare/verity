# ONBOARDING.md — Verity

---

## Document Owner

**Owner:** Eric Hare (Verity)
**Review cadence:** every 6 months, or after any major architectural change
**Last reviewed:** 2026-07

---

## 1 — Codebase Purpose

Verity compares two 3-D surface-topography scans (X3P) of forensic marks — bullet lands, cartridge-case breech faces, toolmarks — and returns a calibrated, bounded **likelihood ratio** with region-level attribution. Callers: the Next.js web app (verity.codes), REST clients, and AI agents over MCP. Every comparison produces a JSON-serializable `ComparisonReport`.

---

## 2 — Layer Map

Outermost first:

| Layer | Responsibility | Key symbol |
|---|---|---|
| Web UI (`services/web`) | Render the report; call the API | `compareMarks()` in `lib/api.ts` |
| HTTP API (`services/api`) | Decode uploads, guard, dispatch, serialize | `verity_api.main._run_compare()` |
| Engine comparison (`services/engine`) | Domain dispatch → score + attribution | `verity.compare.compare_with_previews()` |
| Signal processing | Form removal, roughness band, signatures, CMR | `striation_signature()`, `verity.cmr` |
| Decision firewall | Score → bounded LR; scope + config guards | `verity.decision.lr.ScoreLRModel` |
| X3P codec (`crates/verity-x3p`) | Native read/write of scans, wrapped per language | `verity_x3p::read_x3p()` (Rust) |

Sibling services: `verity_catalog` (local-first scan catalog, own FastAPI app in `verity_catalog.api.app`) and `verity_mcp` (stdio MCP server; the API hosts the same tools at `/mcp` via `verity_api.mcp_server`, e.g. `compare_marks()`).

---

## 3 — Execution Lifecycle

**Representative execution:** `POST /v1/compare` with two whole bullets (striated domain).

1. **Entry:** `compare_v1()` (`verity_api.main`) parses the form and calls `_run_compare()`.
2. **Upload guards:** `_read_marks()` size-caps each file (`limits.read_capped()`), validates it (`limits.validate_x3p()`), decodes it via `verity_x3p.read_x3p` inside `_surface_from_bytes()`, and SHA-256-hashes the bytes for provenance.
3. **Offload:** `_offload()` runs `_compute_report()` on a bounded thread pool with a timeout.
4. **Scope guard:** `_scope_check()` → `check_applicability()`; a hard failure (resolution, modality) returns `_refusal_envelope()` instead of an LR.
5. **Reference:** `load_reference_bundle()` (`verity_api.references`) loads the domain's `.npz` + provenance and runs `check_scorer_drift()`.
6. **Scoring:** `compare_bullets_with_previews()` (`verity.compare`) extracts each land's 1-D signature via `_land_fields()` (`remove_form()` → `isolate_roughness()` → `extract_region()`), builds the land×land CCF matrix with `bullet_comparison()` (`verity.aggregate`), and scores it with `ContrastScorer.score()` (diag_contrast).
7. **Calibration:** `build_comparison_report()` (`verity.report`) fits `ScoreLRModel.fit()` on the reference's KM/KNM scores, maps the score through `predict_lr()` under the empirical |log10 LR| bound, and adds a clustered-bootstrap interval via `lr_credible_interval()`.
8. **Response:** the `ComparisonReport` dict plus previews, scope, requested `include=` intermediates, and the `build_recipe()` methods-as-JSON return to the client.

---

## 4 — Domain Vocabulary

| Term | Definition |
|---|---|
| **Domain** | `"striated"` \| `"impressed"` \| `"toolmark"` (`verity.compare.DOMAINS`). Picks both the score statistic and the calibration reference. |
| **Signature** | The 1-D striation profile a striated surface collapses to; `striation_signature()`. |
| **CMR** | Congruent Matching Regions — windows agreeing on one common transform. 2-D for impressed marks (`consensus_members()`), 1-D for toolmarks and striated attribution (`cmr_score_1d()`). |
| **diag_contrast** | The production whole-bullet score: the matched land diagonal minus the off-diagonal background of the CCF matrix; `BulletComparison.diag_contrast`. |
| **Firewall** | The monotone, bounded score→LR calibration (`ScoreLRModel`) plus the refusal to calibrate a score whose config hash doesn't match the reference's. |
| **Reference bundle** | An `.npz` of KM/KNM scores, labels, and cluster IDs with a provenance sidecar; `ReferenceBundle` via `load_bundle()`. |
| **Config hash** | `ScorerConfig.config_hash` — sha256 of the deployed hyperparameters, recorded in every reference and drift-checked at load. |
| **KM / KNM** | Known-match / known-non-match labelled comparisons; they fit the calibration and scope it. |

---

## 5 — Common Change Recipes

### Recipe A — Change a scorer hyperparameter

1. Edit the default on `ScorerConfig` (`verity.decision.scorer_config`) — this changes `config_hash`.
2. Regenerate **all** bundled references: `cd services/engine && uv run verity-build-references` (dry run), then `--write`.
3. Copy the regenerated `.npz` + sidecars into `verity_api/references/`; confirm `check_scorer_drift()` no longer warns.

### Recipe B — Add a new bundled reference

1. Write a builder module in `verity.examples` (pattern: `build_toolmark_reference.build()`), emitting `.npz` + provenance sidecar.
2. Register a script in `services/engine/pyproject.toml` `[project.scripts]` and call it from `build_references.main()`.
3. Add the file + display name to `_REFERENCES` in `verity_api.references`.

### Recipe C — Add a glass-box step endpoint

1. Add a route on the `steps` router (`verity_api.steps`) wrapping one engine function 1:1: inputs as handles via `_surface_or_400()` / `_signature_1d_or_400()`, output via `STORE.put_array()` with a `produced_by` record.
2. Add the path to `_RATE_LIMITED_PATHS` in `verity_api.main`.
3. Reuse the serializers in `verity_api.intermediates` so the step can't drift from the `include=` view.

### Recipe D — Add a new comparison domain

1. Add the domain to `DOMAINS` and a scoring branch in `comparison_score()` **and** `compare_with_previews()` (`verity.compare`).
2. Add its thresholds to `ScorerConfig` (triggers Recipe A's regeneration).
3. Build its reference (Recipe B) — scored with the *same* statistic the branch computes.

---

## 6 — High-Signal Files by Question Type

| Question type | Where to start |
|---|---|
| "How does a comparison run end-to-end?" | `verity_api.main._compute_report()` |
| "Where does score→LR happen?" | `ScoreLRModel.predict_lr()`, `build_comparison_report()` |
| "What are the deployed hyperparameters?" | `ScorerConfig` (`verity.decision.scorer_config`) |
| "How are references built?" | `verity.examples.build_references.main()` |
| "Why was an LR refused?" | `check_applicability()`, `check_scorer_drift()` |
| "Where does X3P parsing live?" | `verity_x3p::read_x3p()` (`crates/verity-x3p`) |

---

## 7 — Known Gotchas

<!-- TODO: drafted from source comments and project history; confirm with Eric Hare. -->

### Changing ScorerConfig silently invalidates every reference

**Rule:** any change to a `ScorerConfig` default changes `config_hash`; regenerate all bundled references before shipping.
**Why:** the query score and the calibration must live on the same scale; the hash is the only link.
**What breaks:** mis-scaled LRs. `check_scorer_drift()` only *warns* by default — it hard-fails only under `VERITY_STRICT_REFERENCE=1`.

### Score statistic and reference must be built the same way

**Rule:** cartridge = CMR-2D count, toolmark = CMR-1D count (not the bullet-land CCF), whole bullets = `diag_contrast`. Never swap a domain's statistic without rebuilding its reference.
**Why:** each reference `.npz` was generated under exactly that statistic (see the per-domain notes in `verity_api.references`).
**What breaks:** a valid-looking but meaningless LR — no exception is raised.

### The bootstrap credible interval is expensive cold

**Rule:** set `VERITY_LR_BOOTSTRAP_N` (and `VERITY_ENSEMBLE_CACHE_DIR` for persistence) in CI and tests.
**Why:** `lr_credible_interval()` bootstraps the reference ~1000× on first use; `_warm_caches()` hides this in prod but not in fresh test processes.
**What breaks:** multi-minute test runs and CI timeouts.

### Isotonic calibration is diagnostic-only

**Rule:** `ScoreLRModel(method="isotonic")` exists only to compute `cllr_min` (the discrimination floor); never deploy it.
**Why:** pool-adjacent-violators overfits references with few sources.
**What breaks:** over-confident LRs on unseen barrels — the failure the logistic + empirical bound prevents.
