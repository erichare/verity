# verity (engine)

The **Verity surface-comparison engine** — domain-general metrology
preprocessing and registration for forensic X3P scans. See
[`docs/data-catalog-plan.md`](../../docs/data-catalog-plan.md) and the project
plan for the full method.

## Phases 1–2b (this package, so far)

- **`Surface`** — a height field (`NaN` = invalid) with a pixel pitch.
- **Preprocessing** (`verity.preprocess`) — form removal (ISO 25178 F-operation)
  and **ISO 16610 Gaussian S/L filtering** that isolates the *individualizing
  roughness band* (NaN-aware; 50 % transmission at the cutoff by construction).
- **Registration** (`verity.registration`) — a `register(source, target, group)`
  dispatcher: 1-D cross-correlation for striated marks, 2-D phase correlation for
  areal marks.
- **Decision** (`verity.decision`) — the transparent **score → likelihood-ratio**
  layer: logistic / PAV calibration plus forensic metrics (`Cllr`, `Cllr_min`,
  EER, AUC, Tippett). Any score (the cross-correlation today, a learned embedding
  later) becomes an auditable, calibrated weight of evidence.
- **Representation** (`verity.representation`, `learn` extra) — a small
  shift-invariant 1-D encoder + contrastive training; its cosine similarity is a
  drop-in score for the decision layer. (See the honest Phase-2b finding below.)
- **`examples/hamby_km_knm.py`** — a sanity anchor on the real Hamby 252 lands.
  With orientation normalization, same-barrel (known-match) bullet pairs score
  **0.58** vs **0.47** for different-barrel (known-non-match) pairs — a **+0.11**
  mean separation. *Without* it the striae are swamped and there is no
  separation, which is precisely why the method needs an orientation front-end.
  Run `uv run verity-demo-hamby` after ingesting `hamby-252` into the catalog.
  (This is a sanity anchor, not the validated matcher — the calibrated
  likelihood-ratio decision arrives with the method layer.)

**Phase-2a validation** (`examples/hamby_validation.py`, `uv run verity-validate-hamby`)
turns the Phase-1 scores into calibrated LRs and characterizes them with a
**barrel-disjoint** (source-disjoint) protocol on Hamby 252, scored with the
production `diag_contrast` statistic: **AUC ≈ 1.0**, **`Cllr` ≈ 0.113**,
`Cllr_min` ≈ 0.004 over 10 held-out-barrel folds — informative, calibrated
weight of evidence from first-principles metrology, with *no learned
representation yet*. It generalizes across studies (e.g. Phoenix PD Ruger P-95
AUC 0.972 / `Cllr` 0.354, Hamby-173 AUC 0.971 / `Cllr` 0.338, both NBTRD).
(`Cllr` < 1 = informative; the `Cllr` − `Cllr_min` gap is the calibration loss
the source-disjoint split exposes — answering the Cuellar et al. 2024 critique on
its own terms.)

**Phase-2b finding** (`examples/hamby_learned.py`, `verity-learn-hamby`): a
learned representation, trained barrel-disjoint on labels bootstrapped from the
Phase-1 matcher, **does *not* beat the cross-correlation baseline on 210 scans** —
it overfits (held-out AUC collapses to ≈ 0.67, `Cllr` ≈ 1). The synthetic
`test_representation` tests confirm the pipeline *does* learn when given enough
signal, so this is a **data limit, not a defect** — an empirical confirmation
that the learned representation needs more data than Hamby alone, and that the
hand-engineered cross-correlation is a strong baseline for clean 1-D striae.

Next: **expand the dataset** (harvest more NBTRD bullet studies) and retest the
learned representation; then the full firearms-proof validation.

## Develop

```bash
cd services/engine
uv venv --python 3.12      # scientific-stack wheels are reliable on 3.12
uv pip install -e ".[dev]"
uv run pytest
```
