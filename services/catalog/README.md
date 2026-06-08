# verity-catalog

The **Verity data catalog**: a normalized catalog + content-addressed store +
ingestion + a REST API for forensic X3P surface scans harvested from NBTRD,
Figshare, and GitHub. See [`docs/data-catalog-plan.md`](../../docs/data-catalog-plan.md)
for the full design.

Local-first by default — SQLite + a local blob directory, no external services —
and deployable to Postgres + object storage by setting `VERITY_CATALOG_*` env
vars, with no code change.

## What's here (Phases A–D)

- **Schema** (`models.py`) — Study → Firearm → Bullet/CartridgeCase →
  Land/Mark → Scan, plus Instrument; same-source (KM/KNM) labels fall out of the hierarchy.
- **Content-addressed store** (`store.py`) — blobs keyed by SHA-256, deduplicated,
  atomic writes; the same hash the catalog records and the API serves as `ETag`.
- **Ingestion** (`ingest.py`, `harvest/`) — manifest-driven: fetch from Figshare or
  the NBTRD direct endpoints, validate every scan with `verity-x3p` (MD5 + metadata),
  hash into the store, and populate the catalog idempotently.
- **CLI** — `verity-catalog init-db`, `info`, `manifests`, `ingest <name> [--limit N]`.
- **REST API** (`api/`) — a FastAPI service (`verity-catalog-api`) with a uniform
  `{success, data, error, meta}` envelope: browse `GET /studies`, `/firearms`,
  `/bullets/{id}/lands`, faceted `/scans`, resolve a dataset by content hash via
  `/datasets/{name}`, stream a scan with `/scans/{id}/x3p`, plus `/healthz` and `/version`.
- **Harvesters** (`harvest/`) — Figshare, GitHub, and a polite NBTRD crawler that
  resolves detail-page GUIDs and the measurement-download endpoint.

> **Note on Hamby + Figshare:** the Hamby sets on Iowa State Figshare are
> *metadata-only* records ("email csafe@iastate.edu to obtain the data"), so they
> aren't directly downloadable. The bundled `hamby252-barrel1-sample` manifest
> instead uses the openly-downloadable NBTRD direct endpoints (the same 12 sample
> scans the CSAFE `nbtrd` R package ships).

## Develop

```bash
cd services/catalog
uv venv
# The 'ingest' extra builds the verity-x3p binding (Rust). The env var is only
# needed until verity-x3p ships abi3 wheels on PyPI (host runs Python 3.14).
PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1 uv pip install -e ".[dev,ingest]"
uv run pytest

# Try a real ingest (downloads two ~2.9 MB Hamby scans from NBTRD):
uv run verity-catalog init-db
uv run verity-catalog ingest hamby252-barrel1-sample --limit 2
uv run verity-catalog info

# Serve the REST API (defaults to $PORT or 8001; browse the docs at /scalar):
uv run verity-catalog-api
```
