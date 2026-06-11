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
- `POST /mcp` — the **remote MCP endpoint** (streamable HTTP, stateless). Exposes the
  same calibrated tools as the stdio server in `services/mcp` —
  `compare_marks`, `detect_mark_type`, `calibrate_score`, `list_references`,
  `scorer_config`, `service_health` — backed by this engine in-process, so the
  calibration firewall, scope guard, and recipe handles carry over. Because it is
  hosted (not on the agent's machine), scans are passed **inline as base64** rather
  than as local file paths. Point an MCP client at `https://api.verity.codes/mcp`.
  DNS-rebinding host validation is off by default; set `VERITY_MCP_ALLOWED_HOSTS`
  (and optionally `VERITY_MCP_ALLOWED_ORIGINS`) to lock it down. See
  [`services/mcp/README.md`](../mcp/README.md#remote-hosted-endpoint).

## Run

```bash
uv run --extra dev verity-api          # serves on 127.0.0.1:8000
# docs at /docs
```

## Calibration references

Each domain calibrates against a small bundled reference population
(`verity_api/references/`); the LR is always scoped to a named dataset. The deployed
service ships three domains: **striated** (pooled bullet-land), **impressed** (Fadul
cartridge cases, CC-BY), and **toolmark** (tmaRks screwdrivers, MIT) — see
`references/NOTICE.md`.
The decision stays in the engine's monotone, empirically-capped LR firewall; this
layer only decodes, dispatches, and serializes.
