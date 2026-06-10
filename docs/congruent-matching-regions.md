# Congruent Matching Regions (CMR)

**Congruent Matching Cells, generalized to any toolmark.**

CMR is Verity's domain-general comparison principle. It takes the idea behind
Song et al.'s **Congruent Matching Cells (CMC)** — the standard cartridge-case
breech-face method — and lifts it off of 2-D cells and fixed translation+rotation
so the *same* algorithm scores striated marks (bullet lands, toolmarks), impressed
marks (breech faces, footwear), and fractured surfaces.

> **Lineage.** CMC (Song, 2013) divides a breech-face impression into a grid of
> **cells**, registers each cell independently against the other scan, and counts
> the cells that agree on a common (x, y, θ) registration — the *congruent
> matching cells*. A genuine match has many congruent cells; a non-match has cells
> scattered at random offsets. CMR keeps that insight verbatim and only
> generalizes two things: a **cell** becomes a **region** of any dimension, and
> the fixed **2-D translation+rotation** becomes any **transformation group**.

## The principle

For two marks `A` and `B`:

1. **Partition** `A` into regions `Rᵢ` (1-D windows of a profile, 2-D grid cells of
   a surface, or 3-D patches of a mesh).
2. **Register** each region independently against `B` over a transformation group
   `G`, recording its best-fit transform `Tᵢ ∈ G` and its registration quality
   `corrᵢ`.
3. **Vote for consensus.** Among the well-registered regions (`corrᵢ ≥ τ`), find
   the largest cluster whose transforms agree to within a tolerance. Its size is
   the **CMR count** — the number of congruent matching regions.
4. **Calibrate.** The CMR count is a *score*; it flows into Verity's existing
   transparent, empirically-capped (ELUB-inspired) score→LR layer like any other score. CMR improves the
   *similarity* stage; it never touches the decision firewall.

A genuine same-source pair has many regions that independently agree on one
geometry; a different-source pair's regions register at inconsistent offsets, so no
large congruent cluster forms. Crucially, **only some regions need to match** —
damaged, smeared, or non-contacting areas simply don't vote, which is why
cell/region methods are robust to partial and degraded marks where a single global
cross-correlation is brittle.

## One algorithm, every modality

The core `cmr_count` operates only on `(transform, corr)` votes — it is completely
domain-agnostic. Each modality supplies a **vote producer** (a partition + a
per-region registration over its group). That is the whole generalization:

| modality      | region            | group `G`              | congruence on    | reduces to        |
|---------------|-------------------|------------------------|------------------|-------------------|
| Striated      | 1-D profile window| 1-D translation        | common lag       | ≈ Chumbley / CMS  |
| Impressed     | 2-D grid cell     | 2-D translation+rotation | (dx, dy, θ)    | ≈ CMC             |
| Fractured     | 3-D mesh patch    | 3-D rigid              | pose             | (research)        |

This maps one-to-one onto the `register(source, target, group)` dispatcher the
architecture already specifies: CMR is that dispatcher applied *per region* plus a
consensus vote.

### What it subsumes

- **2-D / impressed → CMC.** With 2-D grid cells and translation+rotation, CMR
  instantiates CMC's counting principle (the tuned `cmcR` specialist still leads
  on Fadul — see the whitepaper's Table 4). This is the path to close the
  cartridge-case gap: on the Fadul
  consecutively-manufactured slides, Verity's *global* CCFmax reaches AUC 0.91 while
  CMC reaches 1.00, precisely because global correlation is inflated by shared
  subclass structure that cell congruence ignores.
- **1-D / striated → Chumbley / consecutive matching striae.** With 1-D windows and
  a lag, "regions agreeing on a common shift" is the Chumbley validation step and
  the examiner's consecutive-matching-striae (CMS) reasoning.
- **Bullet land aggregation.** The merged `aggregate.py` already scores bullets by
  whether the land-to-land matches lie on a single cyclic diagonal at *consistent
  lags* — congruence at the inter-land level. CMR is the same principle one level
  down (within-land), so the two compose rather than compete.

## Why it's the right abstraction for Verity

- **Unification.** One scorer replaces the two current paths (1-D `align_1d` CCF and
  2-D global CCFmax). Adding a modality means choosing a `(partition, group)`, not
  writing a new comparison.
- **Attribution for free.** The set of congruent regions *is* the explanation —
  "these regions drove the match" — the region-level attribution the platform calls
  for, and the direct analog of the CMS count examiners already trust. No separate
  attribution mechanism.
- **Robustness.** Local registration absorbs partial contact, occlusion/damage, and
  slowly-varying warp that defeat a single global transform.
- **Same firewall.** The CMR count is just a better score into the published,
  calibrated, bounded LR layer — interpretability and the black-box defense are
  unchanged.

## Honest caveats

- **Cost.** Per pair, CMR registers many regions over a transform grid — far more
  than one global FFT (this is why cmcR is slow). Parallelizable, and amortizable by
  caching per-region spectra, but it is the real price.
- **Marginal gain on clean striated.** Where a single global transform already fits
  (clean bullet lands, AUC ≈ 1.0), CMR's discrimination gain is small; its value
  there is robustness and attribution, not raw separation. The discrimination win is
  largest on impressed, partial, and warped marks.
- **Tuning.** Region size, overlap, `corr` threshold, and congruence tolerance are
  hyperparameters; they must be set per modality and reported (they are the analog
  of CMC's `xThresh`/`thetaThresh`/`corrThresh`).
- **Still a similarity, not a verdict.** CMR produces a number; the reportable weight
  of evidence remains the calibrated LR.

## Validation plan (the unification proof)

The claim is *one* scorer across modalities, so the test is one implementation run
two ways, source-disjoint, against the relevant specialist:

1. **Impressed (Fadul cartridge cases).** CMR-2D should move from the global-CCF
   baseline (AUC 0.91, Cllr 0.53) toward CMC (AUC 1.00, Cllr 0.19) — closing the gap
   with the *same generic code*, since CMR-2D ≈ CMC.
2. **Striated (bullet lands / screwdriver toolmarks).** CMR-1D should at least hold
   the global `align_1d` result with the same code — demonstrating one scorer spans
   both physics regimes.
3. **Skeptic checks.** Label-shuffle null → Cllr ≈ 1; the congruent-region overlay
   should land on real shared structure, not artifacts.

Convincing = a single `cmr_score(partition, group)` that reaches CMC-level on
impressed marks **and** holds the striated result, with the congruent regions
doubling as the attribution map.

## Name

**CMR — Congruent Matching Regions.** Chosen to make the lineage explicit: it *is*
Congruent Matching Cells, with "cell" → "region" as the one generalization a reader
needs to grasp. (Considered: *Congruent Matching Elements*; *Mosaic Matching* — more
evocative but it hides the CMC ancestry, which we want front-and-center.)
