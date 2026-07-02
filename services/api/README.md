# verity-api

The Verity comparison HTTP API — the engine-API half of the Phase-5 platform. It
serves the calibrated, bounded **`ComparisonReport`** that the Next.js UI renders.

## Endpoints

- `GET /health` — `{status, engine_version, domains}` (the calibrated domains).
- `POST /detect` — one X3P upload → suggested mark type (`{domain, coherence}`),
  from the striation anisotropy of the scan.
- `POST /compare` — multipart form: `domain` + two X3P uploads (`mark_a`, `mark_b`).
  Decodes with the native `verity_x3p` codec, runs the domain scorer (striated:
  1-D striation CCF; impressed: areal CCF over rotation), calibrates against the
  bundled reference, and returns the report JSON (likelihood ratio + verbal weight
  of evidence + reference diagnostics + provenance + scope statement).
- `/v1/*` — the versioned glass-box API: `POST /v1/compare` (with inspectable
  intermediates via `?include=`), `POST /v1/compare/report.pdf`, `POST /v1/scope`
  (applicability-domain check), `GET /v1/scorer-config`, `GET /v1/references`,
  plus the content-addressed artifact + step endpoints (`/v1/artifacts`,
  `/v1/steps/*`).
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
- `GET /scalar` — the interactive API reference (Scalar); `/` redirects there.
  Swagger UI (`/docs`) and ReDoc (`/redoc`) are also served.

## Run

```bash
uv run --extra dev verity-api          # serves on 127.0.0.1:8000
# API reference at /scalar (also /docs, /redoc)
```

## Configuration

All knobs are environment variables, validated at startup:

- **CORS** — defaults to the local dev origins `http://localhost:3000` and
  `http://127.0.0.1:3000` only (never `*`). Set `VERITY_CORS_ORIGINS`
  (comma-separated) to allow a deployed front end.
- **Rate limiting** — a per-IP sliding window on the upload/compute endpoints
  (`/compare`, `/detect`, `/v1/*` uploads and steps, `/mcp`): default
  120 requests per 60 s, tunable via `VERITY_RATE_LIMIT` /
  `VERITY_RATE_WINDOW_S`. The counter is in-process (fine for a single
  instance); front a shared store (Redis) when scaling horizontally. Behind a
  trusted reverse proxy (Railway, etc.) set `VERITY_TRUST_PROXY_HEADERS=1` so
  the limit keys on the real client IP from `X-Forwarded-For` instead of the
  proxy address.
- **Upload safety** — every upload is treated as hostile: per-file and
  per-request byte caps, a file-count cap, and a zip-bomb guard on the
  decompressed size/ratio (`VERITY_MAX_FILE_BYTES`, `VERITY_MAX_UPLOAD_BYTES`,
  `VERITY_MAX_FILES`, `VERITY_MAX_UNCOMPRESSED_BYTES`,
  `VERITY_MAX_COMPRESSION_RATIO`), plus a compare timeout and concurrency cap
  (`VERITY_COMPARE_TIMEOUT_S`, `VERITY_MAX_CONCURRENCY`). See
  `verity_api/limits.py` for the defaults.

## Calibration references

Each domain calibrates against a small bundled reference population
(`verity_api/references/`); the LR is always scoped to a named dataset. The deployed
service ships three domains: **striated** (pooled bullet-land), **impressed** (Fadul
cartridge cases, CC-BY), and **toolmark** (tmaRks screwdrivers, MIT) — see
`references/NOTICE.md`.
The decision stays in the engine's monotone, empirically-capped LR firewall; this
layer only decodes, dispatches, and serializes.
