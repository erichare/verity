# How Verity is validated

This is the narrative companion to the canonical number registry,
[`headline-numbers.md`](headline-numbers.md). Every figure below matches a row (and
scope label) there or in the [whitepaper](whitepaper/verity-whitepaper.pdf); when a
number and this text ever disagree, the registry wins. Nothing here is a claim about
the error rate of forensic examination, which remains unknown.

## 1. The three protocols

The same reference population produces different numbers under different evaluation
protocols. Quoting them unlabeled looks like a contradiction; labeled, they are three
different — and individually meaningful — claims:

- **In-sample (deployed reference).** The whole-reference fit the live API embeds in a
  report's `reference` block (bullets: Cllr 0.193, AUC 0.984). Train = test, so it is
  *optimistic by construction* — a diagnostic of the deployed calibration, **not a
  validation claim**.
- **Source-disjoint.** No source (barrel, slide, tool) appears in both train and test.
  This is the honest generalization test: for pooled bullet lands, Cllr 0.186 ± 0.126.
  That the in-sample (0.193) and source-disjoint (0.186) figures are nearly identical is
  the headline strength — *low calibration loss*.
- **Frozen open benchmark.** The published, externally-reproducible protocol: frozen
  pairs, `test_frac = 0.4`, `seed = 0`, repeated source-disjoint folds, committed split
  hashes. For bullets (`bullets-v1`) the fold-mean Cllr is 0.205 ± 0.125 — the number an
  outside party reproduces. See [`data-and-benchmark.md`](data-and-benchmark.md).

`Cllr < 1` = informative; the `Cllr − Cllr_min` gap is the calibration loss the
source-disjoint split exposes — answering the Cuellar et al. (2024) critique ("no
discipline yet has a well-characterized error rate") on its own terms: not by claiming
a field error rate, but by characterizing a calibrated weight of evidence on named data
under a stated protocol.

## 2. Bullet lands, walked through

The production scorer is `diag_contrast` — first-principles, no learned
representation. Under a barrel-disjoint protocol (no barrel in both train and test;
reported per study, never pooled across makes), it yields on held-out barrels
**AUC ≈ 1.00 and test Cllr ≈ 0.11 on Hamby-252** — the single strongest study, never to
be quoted as the pooled figure. The pooled four-study source-disjoint Cllr is ≈ 0.19,
and the frozen `bullets-v1` benchmark reproduces ≈ 0.21. Across the four NBTRD bullet
studies (Hamby-252/173, PGPD Beretta, Phoenix Ruger) **test Cllr ≈ 0.11–0.35 at
AUC ≈ 0.97–1.00** (per-study table in the whitepaper's Validation section) — an
informative, calibrated weight of evidence from metrology alone.

The trained `bulletxtrctr` random-forest specialist, run through the identical
protocol, reaches **Cllr ≈ 0.06 on Hamby-252** (0.064 ± 0.015) — the specialist still
leads on its home turf; Verity's contribution on bullets is the calibrated, bounded,
deployable LR layer, not a better matcher.

## 3. How the scorer was selected — and the caveat

`diag_contrast` was selected over the Phase-1 `diag_mean` and a multivariate fusion by
an explicit barrel-disjoint ablation (the `verity-margin` command). Candidly, that
ablation reused the same four studies as the validation above, so a one-shot
confirmation on untouched data was the next milestone (see the whitepaper's
Limitations). **That confirmation has now run — once, as pre-registered.** A frozen
protocol on the Weller cartridge-case set was filed on [OSF](https://osf.io/prjs9)
(2026-07-01) before any Weller scan was parsed, scored, or ingested by any Verity
component — the registration precedes the first Weller-touching commit (see the
pre-registration's Appendix A, "Deviations and transparent-changes log", for a
clarification about a clone side effect). Run unchanged on all 4,465 evaluable pairs
(95 breech-face scans, 11 slides, 0 exclusions), the frozen Fadul-calibrated pipeline
reached **pooled Cllr 0.163** (95% CI 0.147–0.189, cluster bootstrap by slide),
AUC 0.9995 — the pre-registered **H1 (pooled Cllr ≤ 0.45) is supported**. The pooled
figure sits below the within-study Fadul reference (0.343) because Weller separates
strongly and supplies ~37× more same-source pairs; Weller's own within-study
`cartridge-v2` LOSO split isolates it at Cllr 0.045. Published win or lose:
[`weller-preregistration.md`](weller-preregistration.md); every number is in
[`headline-numbers.md`](headline-numbers.md).

## 4. What doesn't work yet

The Phase-2b learned representation, trained barrel-disjoint on 210 Hamby scans,
**does not beat the cross-correlation baseline** — it overfits (held-out AUC collapses
to ≈ 0.67). Synthetic tests confirm the pipeline *does* learn given enough signal: a
**data limit, not a defect**. Next: expand the dataset and retest. Sources: the
whitepaper's Limitations ("The learned representation does not yet beat the
baseline") and [`services/engine/README.md`](../services/engine/README.md); the
deployed system uses the interpretable first-principles baseline.

## 5. Cartridge cases and toolmarks

The frozen open benchmark is the primary quote for both (fold mean, from
[`headline-numbers.md`](headline-numbers.md)):

| Mark family | Frozen split | Cllr | AUC |
|---|---|---|---|
| Cartridge breech faces (Fadul, impressed) | `cartridge-v1` | 0.398 ± 0.202 | 0.922 (0.941 pooled) |
| Screwdriver toolmarks (tmaRks, striated) | `toolmark-v1` | 0.330 ± 0.047 | 0.943 |

**The cartridge cross-protocol gap, explained.** The internal source-disjoint
(cmr_table) protocol reads AUC **0.991** for cartridge — quoted here only after the
benchmark figure and only with its label, per the registry's quoting policy — while
the frozen benchmark reads 0.922 fold-mean / 0.941 pooled. With only 10 same-source
Fadul pairs, per-fold AUC is extremely unstable and the fold rules differ: a small-n
artifact, not two contradictory claims. The field specialist `cmcR` still leads on
Fadul (slide-disjoint Cllr 0.194); CMR-2D → CMC parity is open roadmap.

Toolmarks are the largest, most stable set (≈ 3.5k same-source pairs): source-disjoint
(0.328 ± 0.050) and frozen benchmark (0.330 ± 0.047) agree tightly.

## 6. Reproduce it

- `verity-validation-report` (in [`services/engine`](../services/engine)) regenerates
  the full characterization — Tippett, DET, calibration, and the source-disjoint
  summary — as a court-ready PDF.
- The frozen splits, replication kits, and leaderboard are served at
  [data.verity.codes](https://data.verity.codes) — see
  [`data-and-benchmark.md`](data-and-benchmark.md).

Further reading: [`headline-numbers.md`](headline-numbers.md) (the registry) ·
[whitepaper PDF](whitepaper/verity-whitepaper.pdf) (full method + limitations) ·
[`weller-preregistration.md`](weller-preregistration.md) (pre-registered protocol —
H1 supported, pooled Cllr 0.163).
