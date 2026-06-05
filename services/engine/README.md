# verity (engine)

The **Verity surface-comparison engine** — domain-general metrology
preprocessing and registration for forensic X3P scans. See
[`docs/data-catalog-plan.md`](../../docs/data-catalog-plan.md) and the project
plan for the full method.

## Phases 1–2a (this package, so far)

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
**barrel-disjoint** (source-disjoint) protocol on Hamby 252: **AUC ≈ 0.92**,
**`Cllr` ≈ 0.60**, `Cllr_min` ≈ 0.38 on held-out barrels — informative, calibrated
weight of evidence from first-principles metrology, with *no learned
representation yet*. (`Cllr` < 1 = informative; the `Cllr` − `Cllr_min` gap is the
calibration loss the source-disjoint split exposes — answering the Cuellar et al.
2024 critique on its own terms.)

Next: the **learned representation** — a better score that slots into this same
decision layer — then the full firearms-proof validation.

## Develop

```bash
cd services/engine
uv venv --python 3.12      # scientific-stack wheels are reliable on 3.12
uv pip install -e ".[dev]"
uv run pytest
```
