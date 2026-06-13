# Verity — canonical headline numbers

**One place for every number we quote.** Each figure is labeled with the *exact
protocol* it came from, because the same reference produces different numbers under
different evaluation protocols and quoting them unlabeled looks like a contradiction.
When a surface (README, whitepaper, web, slides) quotes a validation number, it must
match a row here or carry the same scope label.

Sources are all committed and recomputable:
- **In-sample (deployed reference)** — the `diagnostics` block of each
  `services/api/verity_api/references/*.provenance.json`; this is the whole-reference
  fit the live API embeds in a report's `reference` block. *Optimistic by construction*
  (train = test); it is **not** a validation claim.
- **Source-disjoint (whitepaper)** — `docs/whitepaper/data/cmr_table.json`, recomputed
  from the committed reference under a leave-source-out path.
- **Frozen benchmark** — `services/catalog/benchmarks/<split>/provenance.json`
  `verity_baseline`; the **published, externally-reproducible** protocol (frozen pairs,
  `test_frac=0.4`, `seed=0`, repeated source-disjoint folds). Numbers are the mean over
  folds unless marked *pooled*.
- **Single study / specialist baselines** — whitepaper Table + `baselines.json`.

`Cllr < 1` = informative; `Cllr − Cllr_min` = calibration loss; lower Cllr is better.

---

## Bullet lands — striated (`bullet_pooled.npz`; Hamby-252 & 173, PGPD Beretta, Phoenix)

`n_km = 146`, `n_knm = 1755`.

| Protocol | Cllr | Cllr_min | AUC |
|---|---|---|---|
| In-sample (deployed reference) | 0.193 | 0.168 | 0.984 |
| Source-disjoint (whitepaper / cmr_table) | 0.186 ± 0.126 | — | 0.989 |
| **Frozen benchmark `bullets-v1`** (fold mean) | **0.205 ± 0.125** | 0.136 | 0.979 |
| Single study — Hamby-252 alone, barrel-disjoint | **0.113 ± 0.066** | — | 1.000 |
| Specialist `bulletxtrctr`, Hamby-252 (same protocol) | 0.064 ± 0.015 | — | ≈1.000 |

**Read this as:** pooled in-sample (0.193) and pooled source-disjoint (0.186) are nearly
identical — *low calibration loss, the headline strength*. The frozen benchmark (0.205)
is the number an outside party reproduces. "≈0.11" is **Hamby-252 alone**, the single
strongest study — never quote it as the pooled figure. On Hamby-252 the trained
`bulletxtrctr` specialist still leads (0.064); Verity's bullet contribution is the
calibrated, bounded, deployable LR layer, not a better matcher.

## Cartridge breech faces — impressed (`cartridge_fadul.npz`; Fadul 10 slides)

`n_km = 10`, `n_knm = 180`.

| Protocol | Cllr | Cllr_min | AUC |
|---|---|---|---|
| In-sample (deployed reference) | — | 0.070 | 0.997 |
| Source-disjoint (whitepaper / cmr_table) | 0.385 ± 0.187 | — | 0.991 |
| **Frozen benchmark `cartridge-v1`** (fold mean) | **0.398 ± 0.202** | 0.282 | 0.922 |
| Frozen benchmark `cartridge-v1` (pooled) | 0.343 | 0.284 | 0.941 |
| Specialist `cmcR` (slide-disjoint) | 0.194 | — | ≈1.000 |

> **Known cross-protocol gap — flag before the meeting.** Source-disjoint AUC reads
> **0.991** (cmr_table) but the frozen benchmark reads **0.922** fold-mean / **0.941**
> pooled. With only **10 same-source pairs**, per-fold AUC is extremely unstable and the
> fold rules differ (leave-out fraction). This is a small-n artifact, not two
> contradictory claims — but quote the **frozen benchmark** as primary for cartridge and
> say so. `cmcR` (the field specialist) still leads on Fadul; CMR-2D → CMC parity is open
> roadmap.

## Screwdriver toolmarks — striated-toolmark (`toolmark_tmaRks.npz`; tmaRks 56 tool-edges)

`n_km ≈ 3537`, `n_knm ≈ 164k` (benchmark drops a few duplicate/degenerate pairs →
3530 / 163802).

| Protocol | Cllr | Cllr_min | AUC |
|---|---|---|---|
| In-sample (cmr_table) | — | 0.289 | 0.964 |
| Source-disjoint (whitepaper / cmr_table) | 0.328 ± 0.050 | — | 0.957 |
| **Frozen benchmark `toolmark-v1`** (fold mean) | **0.330 ± 0.047** | 0.309 | 0.944 |
| Frozen benchmark `toolmark-v1` (pooled) | 0.301 | 0.287 | 0.951 |

**Read this as:** the largest, most stable set (3.5k same-source pairs). Source-disjoint
(0.328) and frozen benchmark (0.330) agree tightly — the cleanest of the three.

---

## The one-line generalization claim

One algorithm (CMR), one frozen scorer config (hash
`ea4ddd513b57ce8a3dd117dabc6d539432f7ddfab382c425837ead8199a6e127`), reduced to three
mark families and validated source-disjoint in each:

| Mark family | Reduction | Frozen-benchmark Cllr (fold mean) |
|---|---|---|
| Bullet lands (striated) | consecutive matching striae (1-D) | 0.205 ± 0.125 |
| Cartridge breech faces (impressed) | congruent matching cells / CMC (2-D) | 0.398 ± 0.202 |
| Screwdriver toolmarks (striated) | Chumbley striae (1-D) | 0.330 ± 0.047 |

These characterize **weight of evidence on the named references**, not field error rates.
