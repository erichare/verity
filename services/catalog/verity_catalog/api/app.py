"""The Verity data-catalog FastAPI application.

A faceted, read-only REST layer over the normalized catalog + content-addressed
blob store, with the uniform ``{success, data, error, meta}`` envelope (success
*and* error, including validation errors), Scalar docs at ``/scalar``, and CORS via
``VERITY_CATALOG_CORS_ORIGINS``. Local-first by default; the same code serves
Postgres + S3/R2 when deployed.
"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from .. import __version__
from .envelope import Envelope
from .routers import benchmark, bullets, datasets, firearms, meta, scans, studies

_DESCRIPTION = """\
**Verity data catalog** — a faceted, reproducible REST API over a normalized
catalog of public-domain forensic surface scans (NBTRD / Figshare), each pinned by
its **SHA-256 content hash**.

Browse the containment hierarchy (`/studies` → `/firearms` →
`/bullets/{id}/lands` → `/scans`), filter scans by caliber, land count, source,
modality, and resolution, and download the exact X3P bytes
(`/scans/{id}/x3p`, `ETag` = content hash). `/datasets/{name}` resolves a named
manifest to a **pinned scan list with content hashes** — the reproducible dataset
the validation harness consumes.

Every response uses the uniform envelope `{success, data, error, meta}`. The data
is U.S. Government work in the public domain; please cite NIST/NBTRD.

Web app: <https://verity.codes>
"""

_TAGS = [
    {"name": "studies", "description": "Top-level studies (datasets)."},
    {"name": "firearms", "description": "Barrels within a study — the KM/KNM identity boundary."},
    {"name": "bullets", "description": "Bullet lands (LEAs) and cartridge-case marks."},
    {"name": "scans", "description": "Faceted scan search, metadata, and X3P blob download."},
    {
        "name": "datasets",
        "description": "Named, pinned dataset manifests resolved to content hashes.",
    },
    {
        "name": "benchmark",
        "description": (
            "The open, frozen, source-disjoint benchmark: splits, replication "
            "kits, leaderboards, and submissions (ranked by calibration loss)."
        ),
    },
    {"name": "meta", "description": "Liveness and version."},
]

app = FastAPI(
    title="Verity data catalog",
    version=__version__,
    summary="Faceted, reproducible REST API over a content-addressed catalog of X3P scans.",
    description=_DESCRIPTION,
    contact={"name": "Verity", "url": "https://verity.codes"},
    license_info={"name": "MIT / Apache-2.0"},
    openapi_tags=_TAGS,
)

# The catalog is consumed cross-origin (the verity.codes UI and the validation
# harness), so CORS is required. Default to the production origin; override with
# VERITY_CATALOG_CORS_ORIGINS (comma-separated) for local dev / other fronts.
_cors_origins = [
    o.strip()
    for o in os.environ.get("VERITY_CATALOG_CORS_ORIGINS", "https://verity.codes").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # POST is benchmark submissions only; everything else stays read-only.
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*", "X-Benchmark-Token"],
    expose_headers=["ETag"],
)


# --- Envelope exception handlers: every error is {success:false, error} ----- #
def _error(status_code: int, message: str) -> JSONResponse:
    body = Envelope[None](success=False, data=None, error=message, meta=None)
    return JSONResponse(status_code=status_code, content=body.model_dump())


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return _error(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Compact, client-readable summary of the validation failures.
    parts = [
        f"{'.'.join(str(p) for p in err.get('loc', []))}: {err.get('msg', '')}".strip(": ")
        for err in exc.errors()
    ]
    return _error(422, "; ".join(parts) or "validation error")


@app.exception_handler(Exception)
async def _unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    # Don't leak internals; log-friendly message only.
    return _error(500, f"internal error: {type(exc).__name__}")


# --- Routers ---------------------------------------------------------------- #
app.include_router(studies.router)
app.include_router(firearms.router)
app.include_router(bullets.router)
app.include_router(scans.router)
app.include_router(datasets.router)
app.include_router(benchmark.router)
app.include_router(meta.router)


# --- Docs ------------------------------------------------------------------- #
_SCALAR_HTML = """<!doctype html>
<html>
  <head>
    <title>Verity data catalog — API reference</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
  </head>
  <body>
    <script id="api-reference" data-url="/openapi.json"></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>"""


@app.get("/scalar", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    """A modern API reference (Scalar). Swagger UI (/docs) and ReDoc (/redoc) are
    also available."""
    return HTMLResponse(_SCALAR_HTML)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/scalar")


def run() -> None:
    """``verity-catalog-api`` entry point — serve with uvicorn on $PORT."""
    import uvicorn

    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("verity_catalog.api.app:app", host="0.0.0.0", port=port, reload=False)
