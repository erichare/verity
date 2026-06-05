# verity-catalog

The **Verity data catalog**: a normalized catalog + content-addressed store +
(soon) REST API for forensic X3P surface scans harvested from NBTRD and
Figshare. See [`docs/data-catalog-plan.md`](../../docs/data-catalog-plan.md) for
the full design.

Local-first by default — SQLite + a local blob directory, no external services —
and deployable to Postgres + object storage by setting `VERITY_CATALOG_*` env
vars, with no code change.

## Phase A (this package, so far)

- **Schema** (`models.py`) — Study → Firearm → Bullet/CartridgeCase →
  Land/Mark → Scan, plus Instrument; same-source labels fall out of the hierarchy.
- **Content-addressed store** (`store.py`) — blobs keyed by SHA-256, deduplicated,
  atomic writes; the same hash the catalog records and the API will serve as `ETag`.
- **CLI** — `verity-catalog init-db`, `verity-catalog info`.

Still to come: Figshare ingest (Phase B), the FastAPI REST API (Phase C), the
NBTRD harvester (Phase D).

## Develop

```bash
cd services/catalog
uv venv && uv pip install -e ".[dev]"
uv run verity-catalog init-db
uv run verity-catalog info
uv run pytest
```
