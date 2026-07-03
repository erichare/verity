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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from .. import __version__
from .body_limit import BodySizeLimitMiddleware
from .envelope import Envelope
from .head import HeadRequestMiddleware
from .routers import benchmark, bullets, datasets, firearms, meta, scans, studies

_DESCRIPTION = """\
**Verity data catalog** — a faceted, reproducible REST API over a normalized
catalog of openly licensed forensic surface scans, each pinned by its **SHA-256
content hash**.

Browse the containment hierarchy (`/studies` → `/firearms` →
`/bullets/{id}/lands` + `/cartridge-cases/{id}/marks` → `/scans`), filter scans
by caliber, land count, source, modality, and resolution, and download the exact
X3P bytes (`/scans/{id}/x3p`, `ETag` = content hash). Blobs sync to the public
store in batches, so each scan reports `blob_available` — whether its bytes are
downloadable right now — and `/scans` takes a `blob_available` filter; metadata
is always served. `/datasets/{name}` resolves a named manifest to a **pinned
scan list with content hashes** — the reproducible dataset the validation
harness consumes.

Every response uses the uniform envelope `{success, data, error, meta}`.

**Licensing is per source** (the `source` field on studies and scans says which
applies):

- `nbtrd` — NIST Ballistics Toolmark Research Database scans: U.S. Government
  work in the public domain; please cite NIST/NBTRD.
- `csafe-isu` — CSAFE-ISU cartridge-case scans
  (github.com/CSAFE-ISU/cartridgeCaseScans): CC BY 4.0.
- `tmarks` — tmaRks toolmark profiles (github.com/heike/tmaRks): MIT.
- `figshare` — CSAFE virtual kits (DOI 10.25380/iastate.30854414): CC BY 4.0.

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

# Refuse oversized request bodies (benchmark submissions) with 413 before
# parsing; cap configurable via VERITY_CATALOG_MAX_BODY_BYTES. Registered before
# CORS so CORS stays outermost and 413 responses still carry CORS headers.
app.add_middleware(BodySizeLimitMiddleware)

# Answer HEAD on every GET route (RFC 9110): monitors and link checkers probe
# the kit downloads with HEAD and previously got 405. Registered here so routing
# (inner) sees GET while CORS + security headers (outer) still run normally.
app.add_middleware(HeadRequestMiddleware)

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


# Security headers on every response. No restrictive `default-src` CSP: FastAPI's /docs
# (Swagger UI) loads its bundle from a CDN, so we set `frame-ancestors 'none'` (anti-clickjacking)
# plus the safe transport headers. Decorator-registered, so it stays outermost and wraps CORS.
_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "frame-ancestors 'none'",
}


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


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
# The same Evidence-themed Scalar shell as api.verity.codes/scalar, so the two
# reference pages read as one product. The Scalar bundle is pinned to an exact
# version with subresource integrity; to bump it, recompute the hash:
#   curl -s https://cdn.jsdelivr.net/npm/@scalar/api-reference@<ver>/dist/browser/standalone.js \
#     | openssl dgst -sha384 -binary | base64
_SCALAR_DESCRIPTION = (
    "Verity data API — the open catalog and frozen benchmark splits: faceted search "
    "over content-addressed forensic X3P scans, pinned dataset manifests, replication "
    "kits, and the public leaderboard."
)
_SCALAR_HTML = f"""<!doctype html>
<html lang="en">
  <head>
    <title>Verity data API reference</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content="{_SCALAR_DESCRIPTION}" />
    <meta property="og:title" content="Verity data API reference" />
    <meta property="og:description" content="{_SCALAR_DESCRIPTION}" />
    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://data.verity.codes/scalar" />
    <meta property="og:site_name" content="Verity" />
    <link rel="icon" type="image/svg+xml" href="https://verity.codes/icon.svg" />
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
      /* Evidence palette — Scalar custom-theme variables (paper-first). theme:none
         in the config below disables Scalar's built-in presets so these take effect. */
      :root {{
        --scalar-color-1: #13243a;            /* ink */
        --scalar-color-2: #5a6677;            /* muted */
        --scalar-color-3: #626c7b;            /* 4.71:1 on --scalar-background-1 (WCAG AA) */
        --scalar-color-accent: #0e2a47;       /* navy primary */
        --scalar-background-1: #f4f1ea;       /* canvas / bone */
        --scalar-background-2: #ece7db;       /* panel */
        --scalar-background-3: #e3ddcf;
        --scalar-border-color: rgba(19, 36, 58, 0.14);
        --scalar-button-1: #0e2a47;
        --scalar-button-1-color: #f4f1ea;
        --scalar-color-green: #a9803e;        /* brass — GET */
        --scalar-color-blue: #0e2a47;         /* navy — POST */
        --scalar-color-red: #7a2e2e;          /* oxblood — errors / DELETE */
        --scalar-color-orange: #a9803e;
        --scalar-font: 'Inter', ui-sans-serif, system-ui, sans-serif;
        --scalar-font-code: 'IBM Plex Mono', ui-monospace, monospace;
      }}
      .dark-mode {{
        --scalar-color-1: #e8e2d4;
        --scalar-color-2: #9aa6b6;
        --scalar-color-3: #8a93a3;            /* 5.97:1 on the dark background */
        --scalar-color-accent: #6e97c4;       /* lifted steel — navy is invisible on dark */
        --scalar-background-1: #0c1420;
        --scalar-background-2: #11203b;
        --scalar-background-3: #16263b;
        --scalar-border-color: rgba(232, 226, 212, 0.12);
        --scalar-button-1: #173b5e;
        --scalar-button-1-color: #e8e2d4;
        --scalar-color-green: #c9a063;
        --scalar-color-blue: #6e97c4;
        --scalar-color-red: #c76b6b;
      }}
    </style>
  </head>
  <body>
    <noscript>
      <p>
        This interactive API reference needs JavaScript. The raw OpenAPI document
        is available at <a href="/openapi.json">/openapi.json</a>.
      </p>
    </noscript>
    <script
      id="api-reference"
      data-url="/openapi.json"
      data-configuration='{{"theme":"none","darkMode":false}}'></script>
    <script
      src="https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.62.2/dist/browser/standalone.js"
      integrity="sha384-eL3WJPzR+jPCLfuBs+/9g7eBP2h8PLbtoiFB7e9vX8L3NO9I3qg+T4yPhCACQixp"
      crossorigin="anonymous"></script>
  </body>
</html>"""


@app.get("/scalar", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    """A modern API reference (Scalar). Swagger UI (/docs) and ReDoc (/redoc) are
    also available."""
    return HTMLResponse(_SCALAR_HTML)


@app.get("/robots.txt", include_in_schema=False)
def robots_txt() -> PlainTextResponse:
    """Crawlers may fetch everything; no sitemap line — this is an API host
    (the sitemap lives on the web host)."""
    return PlainTextResponse("User-agent: *\nAllow: /\n")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/scalar")


def run() -> None:
    """``verity-catalog-api`` entry point — serve with uvicorn on $PORT."""
    import uvicorn

    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run("verity_catalog.api.app:app", host="0.0.0.0", port=port, reload=False)
