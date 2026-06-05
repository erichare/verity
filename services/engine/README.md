# verity (engine)

The **Verity surface-comparison engine** — domain-general metrology
preprocessing and registration for forensic X3P scans. See
[`docs/data-catalog-plan.md`](../../docs/data-catalog-plan.md) and the project
plan for the full method.

## Phase 1 (this package, so far)

- **`Surface`** — a height field (`NaN` = invalid) with a pixel pitch.
- **Preprocessing** (`verity.preprocess`) — form removal (ISO 25178 F-operation)
  and **ISO 16610 Gaussian S/L filtering** that isolates the *individualizing
  roughness band* (NaN-aware; 50 % transmission at the cutoff by construction).
- **Registration** (`verity.registration`) — a `register(source, target, group)`
  dispatcher: 1-D cross-correlation for striated marks, 2-D phase correlation for
  areal marks.
- **`examples/hamby_km_knm.py`** — a sanity anchor on the real Hamby 252 lands.
  With orientation normalization, same-barrel (known-match) bullet pairs score
  **0.58** vs **0.47** for different-barrel (known-non-match) pairs — a **+0.11**
  mean separation. *Without* it the striae are swamped and there is no
  separation, which is precisely why the method needs an orientation front-end.
  Run `uv run verity-demo-hamby` after ingesting `hamby-252` into the catalog.
  (This is a sanity anchor, not the validated matcher — the calibrated
  likelihood-ratio decision arrives with the method layer.)

Later phases add the learned representation and the calibrated likelihood-ratio
decision layer.

## Develop

```bash
cd services/engine
uv venv --python 3.12      # scientific-stack wheels are reliable on 3.12
uv pip install -e ".[dev]"
uv run pytest
```
