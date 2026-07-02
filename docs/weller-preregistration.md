# Pre-registration — external validation of the frozen impressed-mark pipeline on the Weller cartridge-case set

> **Status: DRAFT for OSF filing (not yet registered).** This protocol is filed on OSF by
> E. Hare **before** any `wellerMasked` scan is downloaded, parsed, scored, or ingested by
> any Verity component. The OSF registration timestamp preceding the first Weller-touching
> git commit is the integrity claim of this study; §7 defines how to audit it. The result
> is published **win or lose** (§6).

Section numbering follows the OSF Preregistration template (Study Information → Design
Plan → Sampling Plan → Variables → Analysis Plan) so the text can be pasted
field-by-field into the OSF form.

| Registration field | Value |
|---|---|
| Working title | External validation of a frozen, calibrated likelihood-ratio pipeline for cartridge-case breech-face comparison on an independent study (Weller et al. 2012 scans) |
| Registration form | OSF Preregistration |
| Data-collection status | Data exist (public repository) but **have not been accessed** by the authors beyond public metadata (§3.2) |
| Authors | Eric Hare (Verity, verity.codes) |
| License | CC-BY 4.0 |
| Subjects / tags | forensic science; firearms identification; likelihood ratio; calibration; Cllr; external validation; cartridge cases; breech face |

---

## 0. Frozen artifacts this registration pins

The system under test is the Verity impressed-mark pipeline **exactly as committed and
deployed** at registration time. These identifiers freeze it:

| Artifact | Value |
|---|---|
| Scorer-config hash (frozen across all Verity mark families) | `ea4ddd513b57ce8a3dd117dabc6d539432f7ddfab382c425837ead8199a6e127` |
| Calibration reference | `services/api/verity_api/references/cartridge_fadul.npz` — "Fadul cartridge cases (10 consecutively-manufactured slides)" |
| Reference file SHA-256 | `08133ee1dddc41ea1a9ebb32febb83a785c0b420786d26a404eeb7b8b342ec7c` |
| Reference generator | `build_cartridge_fadul_reference` at engine commit `cdec955` (provenance sidecar: `cartridge_fadul.provenance.json`) |
| Score kind | CMR-2D (congruent-matching-cells reduction of Congruent Matching Regions; Song 2013 lineage) |
| Within-study baseline | Frozen benchmark `cartridge-v1`, split hash `31aea8c30185259071988e43af7286dd8de391af86a18385a1470d0ef213bc6c`: Cllr **0.398 ± 0.202** (mean ± SD over 10 folds), pooled Cllr 0.343, AUC 0.922 fold-mean / 0.941 pooled, n_km = 10, n_knm = 180 |
| Metric implementations | `services/engine/verity/decision/metrics.py::cllr`, `services/engine/verity/decision/lr.py::cllr_min` (PAV), `ScoreLRModel.predict_lr` (empirical LR cap) |
| Repository state at drafting | `github.com/erichare/verity` commit `06279d7` |

The runtime scorer-config drift guard (`verity.decision.check_scorer_drift`) refuses a
calibrated LR if the deployed scorer config does not hash to the value above, so the
freeze is enforced by the software, not only by this document.

## 1. Study information

### 1.1 Background

Verity reports forensic surface comparisons as **calibrated likelihood ratios (LRs) on a
named reference population**, never as categorical match/non-match conclusions. The
impressed-mark (cartridge breech-face) domain is calibrated on the Fadul et al. (2011)
scans — 40 scans from 10 consecutively manufactured Ruger P95 pistol slides — and its
within-study, source-disjoint performance is published in the frozen open benchmark
`cartridge-v1` (§0).

Every impressed-mark validation to date reuses the Fadul study. The standing external
criticism of the field (and our own stated top gap, `docs/meeting-readout-carriquiry.md`)
is the absence of **independent external validation**: performance of a *frozen* system
on data from a different study, with no opportunity for tuning. This study supplies that
test, following the validation logic for evaluative LR methods of Meuwly, Ramos &
Haraksim (2017): a fixed method, an independent validation set, and pre-specified
performance characteristics with acceptance criteria.

The validation set is the Weller et al. (2012) cartridge-case scans (`wellerMasked`,
CSAFE-ISU/cartridgeCaseScans): 95 breech-face scans organized under 11 slide identifiers
(TW01–TW11), from the study "Confocal Microscopy Analysis of Breech Face Marks on Fired
Cartridge Cases from 10 Consecutively Manufactured Pistol Slides," CC-BY 4.0, with
FiX3P breech-face masks included.

**What "external" means here — stated precisely.** Both the Fadul and Weller studies used
consecutively manufactured **Ruger P95** slides, and both scan collections were captured
on **NanoFocus µsurf confocal microscopes**. This is therefore **not** a
cross-manufacturer or cross-instrument-family claim. It is a two-study external
validation: an independent production run of slides, an independent firing campaign,
different laboratories and operators, and different acquisition sessions (Weller
collection scanned 2009-09-23 by T. Weller; Fadul collection scanned 2011-01-24 by
X. A. Zheng, per the dataset metadata). The calibration reference contains no Weller
data, so every Weller pair is out-of-sample by construction.

### 1.2 Research question

Does the frozen, Fadul-calibrated Verity impressed-mark pipeline — applied to an
independent study's scans with **zero refitting** — still produce informative,
usefully calibrated likelihood ratios?

### 1.3 Hypothesis

**H1 (primary, confirmatory).** Applied unchanged to all evaluable Weller breech-face
pairs (§5.5 defines "evaluable"), the frozen pipeline attains **pooled Cllr ≤ 0.45**.

The decision rule and threshold justification are pre-specified in §5.1. Secondary
performance characteristics (discrimination/calibration decomposition, AUC, misleading
evidence rates, uncertainty) are pre-specified in §5.2 and reported regardless of the
primary outcome.

**Pre-registered interpretation vocabulary.** To prevent post-hoc spin, the published
result will use exactly one of these labels:

- **Pooled Cllr ≤ 0.45** — "the frozen pipeline transferred to an independent study at
  near within-study performance"; H1 supported.
- **0.45 < pooled Cllr < 1** — "the frozen pipeline remained informative on an
  independent study but degraded beyond the registered threshold"; H1 not supported.
- **Pooled Cllr ≥ 1** — "the frozen pipeline failed to transfer (uninformative or
  miscalibrated)"; H1 not supported.

## 2. Design plan

### 2.1 Study type

Registered computational analysis of existing, publicly available data (secondary data
analysis). No human subjects; no data collection. One-shot design: the frozen system is
applied to the validation set once, and the first complete run under the registered
protocol is the reported result.

### 2.2 Blinding and analyst degrees of freedom

Ground-truth labels (same slide / different slide) are determined mechanically by the
dataset's directory structure (§4.2), not by analyst judgment. Because every component of
the pipeline is frozen by hash **before the data are accessed** (§0), there are no
tunable analysis parameters: no thresholds, masks, preprocessing settings, calibration
refits, or model choices can respond to the Weller data. The only analyst-facing choices
— pair enumeration, exclusion handling, metrics — are fixed a priori in §4–§5.

### 2.3 The system under test and the no-refit rule

The unit scored is a pair of breech-face scans. For each pair, the deployed pipeline:

1. parses each X3P and applies the dataset-provided FiX3P breech-face mask **as shipped**
   (no re-masking);
2. runs the committed impressed-mark preprocessing and the CMR-2D comparison score under
   the frozen scorer config (`ea4ddd…`);
3. maps the score to a likelihood ratio with the calibration fit to the Fadul reference
   (`cartridge_fadul.npz`), including the **empirical LR cap** (the LR is clipped to what
   the reference data can support; bound-limited LRs are flagged) and the
   **out-of-domain scope guard** (a scan outside the reference's resolution/modality
   envelope is refused rather than extrapolated).

The **capped point LR that the deployed API would report is the quantity validated** —
the cap and the scope guard are part of the system under test, not nuisances to be
removed.

**No-refit rule.** No parameter of steps 1–3 — scorer config, calibration map, cap,
guard thresholds, preprocessing — may change in response to any Weller datum. The
reference `.npz` must be byte-identical to the SHA-256 in §0 throughout the analysis. Any
Weller-specific code needed for ingest (e.g., the nested per-slide directory harvest
noted in `docs/toolmark-roadmap.md`, file-name parsing) affects only data loading and
labeling, never scoring or calibration; it will be committed and reviewable.

## 3. Sampling plan

### 3.1 Data source, provenance, and licensing

- **Dataset:** `wellerMasked` in `github.com/CSAFE-ISU/cartridgeCaseScans` (CC-BY 4.0).
  95 X3P breech-face scans with FiX3P masks, organized in 11 slide directories
  (TW01–TW11). Scans captured on a NanoFocus µsurf confocal microscope, 2009-09-23,
  by T. Weller; digitized/published by CSAFE.
- **Underlying study:** Weller, Zheng, Thompson & Tulleners (2012), *Journal of Forensic
  Sciences* 57: 912–917 — ten consecutively manufactured Ruger P95 slides.
- **Note (declared a priori):** the repository contains **eleven** slide directories
  while the study title describes **ten** consecutively manufactured slides. We treat
  each directory as one distinct source (§4.2) regardless of how the eleventh maps to
  the study design, and will report the mapping as documented in the dataset metadata
  at ingest. This choice cannot be influenced by scores: it is fixed here, before access.
- **Calibration data (already held, not part of the validation set):** `fadulMasked`,
  same repository, CC-BY 4.0; Fadul et al. (2011), NIJ report NCJ 237960.

Attribution required by CC-BY will be carried in the catalog's provenance records, as
for every other Verity dataset.

### 3.2 Existing-data / prior-access declaration

As of registration, no `wellerMasked` X3P file has been downloaded, parsed, scored, or
ingested by any Verity component or by the authors. The authors have inspected only
public repository **metadata**: the README (scan counts, instrument, license, study
citations) and the directory listing (TW01–TW11 structure). No surface data and no
quantity derived from surface data has been observed.

### 3.3 Sample size and rationale

All of it. The validation set is every evaluable scan in `wellerMasked` (target: all 95).
There is no sampling, no subsetting, and no stopping rule. Expected scale, conditional on
all scans being attributable known-source scans: 95 scans → 4 465 unordered pairs; the
same-source pair count depends on per-slide scan counts (≈ 300–400 if roughly balanced)
— in any case an order of magnitude more same-source pairs than the 10 that limit the
within-study Fadul benchmark, which is what makes this the more stable impressed-mark
estimate to date. Exact counts will be reported (§6).

### 3.4 Ingest procedure and timestamp discipline

Ingest uses the existing `services/catalog` manifest path (with the nested-directory
harvest extension), recording content hashes and CC-BY provenance per scan — after the
OSF registration is filed. The ordering constraint is absolute:

**OSF registration timestamp < first git commit introducing any Weller-derived artifact**
(manifest entries, cached scans, catalog rows, scores, references, benchmark splits).

## 4. Variables

### 4.1 Unit of analysis

The unordered pair of distinct breech-face marks (one mark = one scan, as in
`cartridge-v1`). All pairs among evaluable scans are enumerated — the same enumeration
rule as the committed benchmark builder (`build_benchmark_splits.py`).

### 4.2 Ground-truth label (independent variable)

`same-source (KM)` iff both scans sit in the same TW slide directory; `different-source
(KNM)` otherwise. Scans not attributable to exactly one slide directory (e.g., any
questioned/unknown-source files, should they exist) are excluded from enumeration and
counted (§5.5).

### 4.3 Outcome (dependent variable)

Per pair: the deployed pipeline's **capped point likelihood ratio** (§2.3), plus its
bound-hit flag and scope-guard status. From the LR set, the primary metric:

**Cllr** (log-likelihood-ratio cost; Brümmer & du Preez 2006), computed by the committed
implementation `verity.decision.metrics.cllr`:

Cllr = ½ · [ mean over KM pairs of log₂(1 + 1/LR) + mean over KNM pairs of log₂(1 + LR) ]

Cllr < 1 means the system is informative; lower is better; Cllr is prior-free and
proper — it penalizes both poor discrimination and miscalibration, which is exactly what
a transferred-calibration claim must survive.

## 5. Analysis plan

### 5.1 Primary (confirmatory) analysis and decision rule

1. Enumerate all evaluable pairs (§4.1–4.2, exclusions §5.5).
2. Score every pair with the frozen pipeline (§2.3). No refitting of any kind.
3. Compute **pooled Cllr** over all scored pairs.
4. **Decision rule: H1 is supported iff the pooled point estimate ≤ 0.45.** The
   uncertainty interval (§5.2) is reported alongside but the registered decision is on
   the point estimate — one number, no discretion.

**Threshold justification (why 0.45).** The within-study, source-disjoint baseline on
the same reference is fold-mean Cllr 0.398 ± 0.202 (`cartridge-v1`, §0), pooled 0.343.
The threshold 0.45 ≈ fold-mean + 0.25 fold-SD: it permits only modest degradation
(≈ 13% relative) from within-study performance despite the move to an independent
study, and sits far below the uninformative bound (Cllr = 1). It is deliberately
**conservative in the direction of failure**: a system that merely "remains somewhat
informative" out-of-study (e.g., Cllr 0.6–0.9) does *not* pass. We consider a
pre-registered miss at this bar more valuable than a pass at a soft one.

### 5.2 Secondary analyses (pre-specified; reported regardless of outcome)

On the same scored pairs:

- **Discrimination/calibration decomposition:** Cllr_min (PAV-optimal recalibration
  floor, `cllr_min`) and calibration loss = Cllr − Cllr_min. This separates "the CMR-2D
  score transfers" from "the Fadul calibration transfers" — if H1 fails, this localizes
  why.
- **AUC** of the scores (pooled), and **ECE** as computed by the committed benchmark
  scorer (`verity.benchmark.score_submission`).
- **Misleading-evidence rates:** share of KM pairs with LR < 1 (RMED) and of KNM pairs
  with LR > 1 (RMEP).
- **Empirical-cap engagement:** fraction of pairs whose LR was bound-limited.
- **Scope-guard refusals:** count and recorded reasons (§5.5).
- **Uncertainty on pooled Cllr:** nonparametric cluster bootstrap over sources —
  resample the 11 slides with replacement (B = 2000, seed 0); per replicate, re-enumerate
  pairs among the resampled slides' scans under the §4.2 rules, treating pairs between
  two copies of the same resampled slide as within-source and excluding them from the
  KNM set; recompute pooled Cllr on the frozen LRs (nothing is refit). Report the 2.5th
  and 97.5th percentiles.

### 5.3 Within-study companion benchmark (secondary, clearly labeled)

After the primary analysis, a frozen open-benchmark split **`cartridge-v2`** (Weller)
will be built with the committed builder under the **identical protocol** as
`cartridge-v1`: `n_splits = 10`, `test_frac = 0.4`, `seed = 0`, the same source-disjoint
fold rule and submission contract, published to `services/catalog/benchmarks/` with its
split hash and provenance. Verity's baseline row for that split uses the benchmark's
leave-sources-out calibration **within Weller** — a *within-study* number under the
benchmark contract, reported separately from and never conflated with the external
(frozen-Fadul-calibration) result of §5.1. Both numbers appear in
`docs/headline-numbers.md` with explicit protocol labels.

### 5.4 Exploratory analyses

Anything beyond §5.1–5.3 (per-slide breakdowns, score distribution comparisons against
Fadul, mask-sensitivity probes, error-case forensics) is exploratory, will be labeled
exploratory, and grounds no claims.

### 5.5 Exclusion rules (fixed a priori; all counts published)

A scan or pair is excluded **only** by these mechanical rules — never because of its
score or LR:

1. **Unparseable/corrupt:** the X3P fails the committed parser or its integrity checks.
2. **Unattributable:** the scan cannot be assigned to exactly one TW slide directory
   (§4.2).
3. **Duplicate:** identical scan content hash to an already-included scan (the
   benchmark builder's existing dedup rule); first occurrence kept.
4. **Scope-guard refusal:** the deployed guard declines the pair as out-of-domain. The
   refusal is itself a registered outcome of interest and is reported with its reason;
   refused pairs are excluded from the Cllr aggregation because no LR exists for them.

Evaluability floor: if, after rules 1–4, fewer than 50% of the 95 scans or fewer than
30 same-source pairs remain, the study is reported as **"not evaluable as registered"**
(with full counts and reasons) rather than as a pass/fail — publishing that outcome is
covered by the same commitment (§6).

### 5.6 Missing data and failure handling

There is no imputation of any kind. Every excluded scan/pair is enumerated in the
published result with its triggering rule. A pipeline crash on a specific pair (as
opposed to a guard refusal) is treated under rule 1/4 semantics: counted, reported, and
the pair excluded.

### 5.7 What this study does and does not establish

Does: whether a frozen, calibrated LR pipeline transfers across independently produced,
independently fired, independently scanned cartridge-case studies of the same firearm
model and instrument family, with zero tuning. Does **not**: cross-manufacturer or
cross-instrument-family generalization (both studies are Ruger P95 / NanoFocus µsurf);
field error rates; casework performance on degraded or partial marks. All published LRs
characterize weight of evidence **on the named Fadul reference** — not a verdict, not a
field error rate — per the scope note embedded in every Verity report.

## 6. Publication commitment (win or lose)

Whatever the outcome — H1 supported, not supported, or "not evaluable as registered" —
we will, with equal prominence and using the §1.3 vocabulary:

1. add the external-validation result to `docs/headline-numbers.md` as a new
   protocol-labeled row set ("Weller external, frozen Fadul calibration" and, per §5.3,
   "Frozen benchmark `cartridge-v2`"), linking this OSF registration;
2. report the result in a dedicated section of the Verity preprint (arXiv, stat.AP),
   including all §5.2 secondaries and all exclusion counts, linking this OSF
   registration by DOI;
3. publish the `cartridge-v2` frozen split (pairs, folds, split hash, provenance,
   Verity baseline) to the open benchmark so any third party can rescore it;
4. make the result reproducible from the repository (committed artifacts + the
   `make reproduce` path used for all headline numbers).

The existing cartridge quoting policy is unchanged by any outcome: press-facing
materials continue to use bullets-only numbers; cartridge results (including this one)
are quoted with protocol labels in scientific/technical surfaces.

**Deviations.** Any departure from this protocol is documented in an OSF transparent
addendum and in every published surface carrying the result, before or alongside the
result — silent deviations are treated as protocol violations.

## 7. Timeline, roles, and audit trail

| Step | Owner | Constraint |
|---|---|---|
| File this protocol on OSF | E. Hare | Before any Weller data access (§3.2, §3.4) |
| Ingest `wellerMasked` into the catalog | in-repo | First Weller commit strictly after the OSF timestamp |
| One-shot frozen scoring + primary/secondary analyses | in-repo | Reference SHA-256 unchanged (§0); scorer drift guard active |
| `cartridge-v2` split + headline-numbers rows + preprint section | in-repo | Published win or lose (§6) |

Planned window: registration and ingest July 2026; analysis and publication with the
preprint, August 2026.

**Audit trail.** Anyone can verify the ordering claim from public records: the OSF
registration timestamp, versus the first commit in `github.com/erichare/verity` whose
tree contains any Weller-derived artifact. The scorer-config hash and the reference
SHA-256 in §0 bind the scored system to the registered one; the runtime drift guard
(§0) refuses calibrated LRs under any other scorer config.

## References

- Brümmer, N. & du Preez, J. (2006). Application-independent evaluation of speaker
  detection. *Computer Speech & Language* 20(2–3): 230–275.
- Fadul, T. G., Hernandez, G. A., Stoiloff, S. & Gulati, S. (2011). *An Empirical Study
  to Improve the Scientific Foundation of Forensic Firearm and Tool Mark Identification
  Utilizing 10 Consecutively Manufactured Slides.* NIJ report, NCJ 237960.
- Meuwly, D., Ramos, D. & Haraksim, R. (2017). A guideline for the validation of
  likelihood ratio methods used for forensic evidence evaluation. *Forensic Science
  International* 276: 142–153.
- Song, J. (2013). Proposed "NIST Ballistics Identification System (NBIS)" based on 3D
  topography measurements on correlation cells. *AFTE Journal* 45(2): 184–194.
- Weller, T. J., Zheng, X. A., Thompson, R. M. & Tulleners, F. A. (2012). Confocal
  microscopy analysis of breech face marks on fired cartridge cases from 10
  consecutively manufactured pistol slides. *Journal of Forensic Sciences* 57: 912–917.
- CSAFE-ISU, *cartridgeCaseScans* (fadulMasked / wellerMasked), CC-BY 4.0,
  github.com/CSAFE-ISU/cartridgeCaseScans.
- Verity companion documents (this repository): `docs/headline-numbers.md` (canonical
  numbers and quoting policy), `docs/toolmark-roadmap.md` (Weller ingest plan),
  `docs/meeting-readout-carriquiry.md` (stated validation gap),
  `services/catalog/benchmarks/cartridge-v1/provenance.json` (within-study protocol).
