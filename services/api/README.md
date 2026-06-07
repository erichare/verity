# verity-api

The Verity comparison HTTP API — the engine-API half of the Phase-5 platform. It
serves the calibrated, bounded **`ComparisonReport`** that the Next.js UI renders.

## Endpoints

- `GET /health` — `{status, engine_version, domains}` (the calibrated domains).
- `POST /compare` — multipart form: `domain` + two X3P uploads (`mark_a`, `mark_b`).
  Decodes with the native `verity_x3p` codec, runs the domain scorer (striated:
  1-D striation CCF; impressed: areal CCF over rotation), calibrates against the
  bundled reference, and returns the report JSON (likelihood ratio + verbal weight
  of evidence + reference diagnostics + provenance + scope statement).

## Run

```bash
uv run --extra dev verity-api          # serves on 127.0.0.1:8000
# docs at /docs
```

## Calibration references

Each domain calibrates against a small bundled reference population
(`verity_api/references/`); the LR is always scoped to a named dataset. v1 ships
the **impressed** domain (Fadul cartridge cases, CC-BY — see `references/NOTICE.md`).
The decision stays in the engine's monotone, ELUB-bounded LR firewall; this layer
only decodes, dispatches, and serializes.
