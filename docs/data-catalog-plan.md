# Verity Data Catalog — Design & Implementation Plan

## Context

Verity's method must be *trained and validated* on labeled X3P scans, and the firearms-first proof (matching `bulletxtrctr`/`cmcR` on their home turf, measured by `Cllr`) lives or dies on **reproducible, programmatic access to that data**. The primary public well is the **NIST Ballistics Toolmark Research Database (NBTRD/NRBTD)**.

**Research finding (2026-06-05): there is no unified API.** NBTRD is a server-rendered ASP.NET MVC portal behind Cloudflare — no REST/JSON API, no OAI-PMH, no swagger (verified: `/api`, `/swagger`, `/oai`, `/sitemap.xml` all 404; the [JRES 125.004 paper](https://nvlpubs.nist.gov/nistpubs/jres/125/jres.125.004.pdf) only ever calls it a "searchable portal"). The sole existing tool, [`CSAFE-ISU/nbtrd`](https://github.com/CSAFE-ISU/nbtrd), is **pure HTML scraping + Selenium**, unmaintained since 2020. So this needs to be built.

**Three findings make it very buildable:**
1. The data is **U.S. Government work → public domain, freely redistributable** (only a citation request). We can **mirror, normalize, and serve** it — not just proxy.
2. **Downloads need no auth.** One stable endpoint — `GET …/Studies/{Bullet,Cartridge}Measurement/DownloadMeasurement/{guid}` — returns the raw `.x3p`. GUIDs are discoverable only by scraping detail pages, but **once fetched + hashed we never need NIST again**.
3. The highest-value sets (**Hamby**) are already on **Iowa State / CSAFE Figshare with DOIs** — clean, stable access for exactly what the firearms proof needs now.

**Locked decisions (2026-06-05):** local-first REST service · ingest validated sets first · build now while engaging NIST in parallel.

## Goals / non-goals

**Goals:** a clean, documented, **faceted REST API** over a normalized catalog of forensic surface scans; **reproducible dataset snapshots** pinned by content hash (the artifact the Cuellar-proof validation harness consumes); ingest from Figshare DOIs (preferred) and NBTRD (scrape where no DOI mirror exists); validate/normalize every scan with **`verity-x3p`**; **local-first** (runs over SQLite + local files, zero external services) and **deployable later** (Postgres + object store) with no code change.

**Non-goals (v1):** full NBTRD crawl; uploads to NBTRD; running a public hosted service; auth/multi-tenant; modalities beyond what the validated sets contain.

## Architecture

Three layers, Python (the science stack's language), reusing what we built.

### 1. Harvester / ingestion (`verity_catalog.harvest`)
Pluggable **source adapters** behind one interface (`discover() -> records`, `fetch(record) -> bytes`):
- **`FigshareSource`** (preferred) — resolve a DOI/article → file list → download. Clean, stable, versioned.
- **`NbtrdSource`** — crawl the ASP.NET detail pages to harvest measurement **GUIDs + metadata**, download via `DownloadMeasurement/{guid}`. Polite (throttle, custom UA, backoff, retry); isolated so its fragility can't leak. Ports the proven URL logic from `CSAFE-ISU/nbtrd`, robustly.

Every downloaded scan is **validated + metadata-extracted with `verity-x3p`** (the Python binding), **SHA-256 hashed**, written to the content-addressed store, and recorded in the catalog with full provenance (source, NBTRD GUID / Figshare DOI, fetch time). Ingestion is **idempotent** (hash dedupe) and driven by a **manifest** (below).

### 2. Catalog (`verity_catalog.models`, SQLModel/SQLAlchemy + Alembic)
Schema mirroring NBTRD's real 4-level hierarchy, with `source` first-class so the validation harness can build labeled pairs and **source-disjoint splits**:

```
Study ─< Firearm ─< Bullet ─< Land(LEA) ─< Scan
                   └< CartridgeCase ─< {BreechFaceMark, FiringPinMark} ─< Scan
Contributor, Instrument            (shared reference entities)
```

`Scan` carries: modality (`x3p_3d`/`png_2d`), instrument, magnification, **lateral_resolution_x/y**, light_source, the X3P-embedded metadata blob, **content hash**, size, source provenance, and the `firearm_id`/`barrel` that makes same-source (KM) vs different-source (KNM) derivable. Searchable facets match NIST's own: caliber, firearm brand, firing-pin class, breech-face class, n_lands, twist, `persistence`, `consecutively_manufactured`, `nist_measurement`.

### 3. REST API (`verity_catalog.api`, FastAPI)
Auto-OpenAPI, consistent envelope (`{success, data, error, meta}`), pagination:
- `GET /studies`, `/studies/{id}` · `GET /firearms`, `/firearms/{id}`
- `GET /bullets/{id}/lands` · `GET /cartridge-cases/{id}/marks`
- `GET /scans` — faceted filter (`?caliber=&firing_pin_class=&n_lands=&persistence=&min_resolution=&study_id=&source=`) + pagination
- `GET /scans/{id}` (metadata) · `GET /scans/{id}/x3p` (binary, `ETag`=hash) · `GET /scans/{id}/image` (2D png)
- `GET /datasets/{name}` — resolve a **named, pinned dataset** → the exact scan list + hashes (the reproducibility entry point for the validation harness)
- `GET /healthz`, `/version`

Storage + DB are abstracted: **SQLite + local FS by default** (local-first, one command), **Postgres + S3/MinIO** when deployed.

## Reproducibility (the validation tie-in)
A **manifest** (`manifests/<name>.yaml`) is a named dataset recipe: source + DOI/GUID list + **expected SHA-256s**. It is *the* pinned-dataset artifact — `GET /datasets/hamby-44` resolves it; re-running on any machine fetches hash-identical bytes. This is exactly the "pinned data + source-disjoint splits" the firearms proof needs to answer the Cuellar critique.

## v1 ingest targets (validated sets first)
Hamby 44 & 252 (Figshare DOIs) → NIST consecutively-manufactured + persistence studies (NBTRD scrape) → cartridge-case validity corpus (PNAS-2022 / NBIDE) → Phoenix/Houston bullet sets if accessible. Each becomes a manifest.

## NIST engagement (parallel, non-engineering track)
Draft outreach to the NBTRD team (Zheng et al., the JRES authors) via CSAFE relationships, proposing: (a) an **official bulk export / data dump** to retire scraping, and (b) offering the normalized open API + harvester as a **community contribution** they could endorse or host. Tracked in `docs/nist-outreach.md`; build does **not** block on it.

## Build phases (PR per phase, like the bindings)
- **A — Catalog skeleton + store:** data model (SQLModel), Alembic migrations, content-addressed store (local FS, S3-ready), config, `verity-catalog` CLI.
- **B — Figshare ingest + `verity-x3p` validation:** end-to-end ingest of **Hamby 44/252** (download → verify → hash → store → catalog rows, KM/KNM derivable). First reproducible dataset + manifest.
- **C — REST API:** FastAPI endpoints, faceted `/scans` search, blob serving, OpenAPI, the `/datasets/{name}` resolver; `verity-catalog serve` on localhost.
- **D — NBTRD harvester:** robust polite scraper for GUIDs/metadata of the NIST studies not on a DOI mirror; ingest the consecutively-manufactured/persistence + cartridge sets.
- **E — Polish:** manifests for all v1 sets, docs, tests, one-command run (docker-compose for the Postgres/S3 deploy path); draft NIST outreach.

## Critical files (to create)
- `services/catalog/pyproject.toml` · `verity_catalog/config.py` · `verity_catalog/cli.py`
- `verity_catalog/models.py` — the catalog schema (Study→Firearm→Bullet/CC→Land/Mark→Scan)
- `verity_catalog/store.py` — content-addressed blob store (reuses the content-hash pattern)
- `verity_catalog/harvest/base.py` · `harvest/figshare.py` · `harvest/nbtrd.py`
- `verity_catalog/ingest.py` — validate via `verity-x3p`, hash, record provenance
- `verity_catalog/api/app.py` + routers — FastAPI service
- `services/catalog/manifests/hamby-44.yaml`, `hamby-252.yaml`, …
- `services/catalog/alembic/…` · `services/catalog/tests/…`
- `docs/nist-outreach.md` — outreach draft

## Verification
1. **Ingest Hamby 44** from its Figshare DOI → catalog has the expected 210 LEA scans, correct hierarchy, KM/KNM derivable, hashes recorded.
2. **API:** `GET /scans?caliber=9mm%20Luger` returns expected rows; `GET /scans/{id}/x3p` returns an X3P that `verity-x3p` reads **and checksum-verifies**.
3. **Reproducibility:** `GET /datasets/hamby-44` resolves to a pinned list; a clean-machine re-fetch yields **identical hashes**.
4. **Local-first:** the whole thing runs on SQLite + local FS via one command, no Postgres/S3/network beyond the one-time ingest.

## Risks & mitigations
- **Scraper fragility (NBTRD HTML)** → prefer Figshare DOIs; isolate scraping behind a source adapter; **cache/fetch-once**; the `DownloadMeasurement` GET is the stable part; pinned hashes detect breakage.
- **Storage size (GBs)** → local-first + **lazy, manifest-driven** ingest; mirror only validated sets, not everything.
- **Cloudflare/anti-bot** → polite crawl; fall back to seeded GUID lists / DOI mirrors; NIST engagement.
- **Over-building before the method needs it** → v1 scoped to the sets the firearms proof needs; full catalog is a later, separable effort.
- **Provenance/attribution** → public domain, but preserve per-scan provenance and surface NIST citation in API responses + docs.
