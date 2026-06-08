"""Verity comparison API — serves the calibrated :class:`ComparisonReport`.

``POST /compare`` takes two X3P uploads + a domain, decodes them with the native
``verity_x3p`` codec, runs the domain scorer, calibrates against the bundled
reference, and returns the report JSON. ``GET /health`` lists the calibrated
domains. The decision stays in the engine's bounded-LR firewall; this layer only
decodes, dispatches, and serializes. The Next.js UI renders the response.

A versioned ``/v1`` router exposes the same comparison plus, on request
(``include=calibration,features,perland,trace``), the algorithm's **intermediate
computations** — the reference calibration curve with this score on it, the
CCF-matrix structure features, per-land evidence, and the pipeline trace — so the
result is inspectable end to end. ``/v1/scope`` runs the applicability-domain
guard on a single scan. The unversioned routes are preserved as thin aliases.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import verity_x3p
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel

from verity import land_trace
from verity.compare import compare_bullets_with_previews, compare_with_previews
from verity.decision import cached_bootstrap_calibration, check_applicability
from verity.detect import detect_domain
from verity.surface import Surface

from .intermediates import (
    calibration_diagnostics,
    parse_include,
    striated_bullet_intermediates,
    trace_dict,
)
from .references import available_domains, load_reference, load_striated_single_land

_LAMBDA_S, _LAMBDA_C = 4e-6, 250e-6


def _engine_version() -> str:
    try:
        return version("verity")
    except PackageNotFoundError:
        return "unknown"


_DESCRIPTION = """\
**Verity** — calibrated, bounded **likelihood ratios** for forensic surface
comparison, across **striated** marks (bullet lands, toolmarks) and **impressed**
marks (cartridge breech faces).

Upload X3P 3-D topography scans; the engine decodes them with the native
`verity_x3p` codec, scores the comparison, calibrates the score to a likelihood
ratio against a named reference population (with a characterized cost, *Cllr*, and
a bootstrap credible interval), and returns region-level **attribution** — the
parts of the marks that drove the match.

The decision stays behind a glass-box statistical firewall: the reported LR is a
monotone, bounded transform of the score, interpretable regardless of how the score
was computed. It is *not* a claim about the error rate of forensic examination,
which remains unknown.

The versioned **`/v1`** routes expose the algorithm's intermediate steps on request
(`include=calibration,features,perland,trace`) and an applicability-domain guard
(`/v1/scope`).

Web app: <https://verity.codes> · Method & references: <https://verity.codes/#science>
"""

_TAGS = [
    {"name": "compare", "description": "Compare two marks → a calibrated likelihood-ratio report."},
    {"name": "meta", "description": "Service health and mark-type detection."},
    {"name": "v1", "description": "Versioned API: comparison with inspectable intermediates."},
]


def _warm_caches() -> None:
    """Pre-build each bundled reference's bootstrap calibration ensemble so the
    first comparison doesn't pay the credible-interval cost on the request path."""
    try:
        for domain in available_domains():
            scores, labels, _ = load_reference(domain)
            cached_bootstrap_calibration(scores, labels, n_boot=1000, seed=0)
        s_scores, s_labels, _ = load_striated_single_land()
        cached_bootstrap_calibration(s_scores, s_labels, n_boot=1000, seed=0)
    except Exception:  # noqa: BLE001 - warmup is best-effort; never block startup
        pass


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _warm_caches()
    yield


app = FastAPI(
    title="Verity comparison API",
    version="0.1.0",
    summary="Calibrated, bounded likelihood ratios for forensic surface comparison.",
    description=_DESCRIPTION,
    contact={"name": "Verity", "url": "https://verity.codes"},
    license_info={"name": "MIT / Apache-2.0"},
    openapi_tags=_TAGS,
    lifespan=_lifespan,
)


class HealthResponse(BaseModel):
    status: str
    engine_version: str
    domains: list[str]


class DetectResponse(BaseModel):
    domain: str
    coherence: float


# The Next.js UI is a separate origin, so the browser needs CORS. Defaults cover
# local dev (localhost / 127.0.0.1 :3000); override with VERITY_CORS_ORIGINS
# (comma-separated) for a deployed front end.
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "VERITY_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _surface_from_bytes(data: bytes) -> Surface:
    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        s = verity_x3p.read_x3p(path)
        return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)
    except Exception as exc:  # noqa: BLE001 - surface a clean 400 for a bad upload
        raise HTTPException(status_code=400, detail=f"could not read X3P: {exc}") from exc
    finally:
        os.remove(path)


async def _read_surface(upload: UploadFile) -> Surface:
    return _surface_from_bytes(await upload.read())


async def _read_marks(uploads: list[UploadFile]) -> tuple[list[Surface], list[str]]:
    """Decode each upload and content-hash its raw bytes (the provenance spine that
    ties a report back to the exact scanned file)."""
    surfaces: list[Surface] = []
    hashes: list[str] = []
    for f in uploads:
        data = await f.read()
        surfaces.append(_surface_from_bytes(data))
        hashes.append(hashlib.sha256(data).hexdigest())
    return surfaces, hashes


@app.get(
    "/health",
    tags=["meta"],
    summary="Service health + calibrated domains",
    response_model=HealthResponse,
)
def health() -> dict:
    return {"status": "ok", "engine_version": _engine_version(), "domains": available_domains()}


@app.post(
    "/detect",
    tags=["meta"],
    summary="Suggest a mark type from one scan",
    response_model=DetectResponse,
)
async def detect(scan: UploadFile = File(...)) -> dict:
    """Suggest a mark type for one uploaded scan, from striation anisotropy — the
    structure-tensor coherence of its 2-D FFT power (directional striae → `striated`;
    isotropic areal → `impressed`). The UI pre-selects it; the user confirms, since
    the mark type picks the calibration reference."""
    surface = await _read_surface(scan)
    domain, coherence = detect_domain(surface)
    return {"domain": domain, "coherence": round(coherence, 3)}


async def _run_compare(
    domain: str,
    mark_a: list[UploadFile],
    mark_b: list[UploadFile],
    *,
    include: set[str],
) -> dict:
    """Core comparison shared by the unversioned and ``/v1`` routes. ``include``
    selects which intermediate computations to attach (empty = lean report)."""
    if domain not in available_domains():
        raise HTTPException(
            status_code=400,
            detail=f"domain {domain!r} has no calibrated reference; available: {available_domains()}",
        )
    if not mark_a or not mark_b:
        raise HTTPException(status_code=400, detail="provide at least one scan per mark")

    scores, labels, reference_name = load_reference(domain)
    surfaces_a, hashes_a = await _read_marks(mark_a)
    surfaces_b, hashes_b = await _read_marks(mark_b)
    provenance = {
        "api_version": app.version,
        "engine_version": _engine_version(),
        "mark_a": [f.filename for f in mark_a],
        "mark_b": [f.filename for f in mark_b],
        "input_hashes": {"mark_a": hashes_a, "mark_b": hashes_b},
    }

    if domain == "striated":
        if len(surfaces_a) == 1 and len(surfaces_b) == 1:
            s_scores, s_labels, s_name = load_striated_single_land()
            report, previews = compare_with_previews(
                surfaces_a[0],
                surfaces_b[0],
                domain="striated",
                reference_scores=s_scores,
                reference_labels=s_labels,
                reference_name=s_name,
                provenance={**provenance, "n_lands_a": 1, "n_lands_b": 1},
            )
            scores, labels, reference_name = s_scores, s_labels, s_name
        else:
            report, previews = compare_bullets_with_previews(
                surfaces_a,
                surfaces_b,
                reference_scores=scores,
                reference_labels=labels,
                reference_name=reference_name,
                provenance=provenance,
            )
    else:
        report, previews = compare_with_previews(
            surfaces_a[0],
            surfaces_b[0],
            domain=domain,
            reference_scores=scores,
            reference_labels=labels,
            reference_name=reference_name,
            provenance=provenance,
        )

    resp = {**report.to_dict(), "previews": previews}
    if not include:
        return resp

    # Applicability-domain guard (warn mode) on each input — cheap, high-value.
    resp["scope"] = {
        "mark_a": [
            check_applicability(s, domain=domain, mode="warn").to_dict() for s in surfaces_a
        ],
        "mark_b": [
            check_applicability(s, domain=domain, mode="warn").to_dict() for s in surfaces_b
        ],
    }
    if "calibration" in include:
        resp["calibration"] = calibration_diagnostics(scores, labels, report.score, reference_name)
    if domain == "striated" and len(surfaces_a) > 1 and len(surfaces_b) > 1:
        resp.update(
            striated_bullet_intermediates(
                surfaces_a, surfaces_b, include, single_land_reference=load_striated_single_land()
            )
        )
    elif domain == "striated" and "trace" in include:
        resp["trace"] = {
            "a": trace_dict(land_trace(surfaces_a[0], lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)),
            "b": trace_dict(land_trace(surfaces_b[0], lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)),
        }
    return resp


_COMPARE_EXAMPLE = {
    "domain": "striated",
    "score": 0.153,
    "score_kind": "bullet-contrast",
    "likelihood_ratio": 146.0,
    "log10_lr": 2.16,
    "log10_lr_ci_lo": 1.83,
    "log10_lr_ci_hi": 2.16,
    "lr_ci_method": "bootstrap-row-stratified",
    "direction": "same source",
    "verbal": "moderately strong support for same source",
    "lr_bound_log10": 2.16,
    "reference": {
        "name": "pooled bullet-land reference (Hamby-252 & 173, Beretta, Phoenix)",
        "n_km": 146,
        "n_knm": 1755,
        "cllr": 0.193,
        "cllr_min": 0.168,
        "auc": 0.984,
    },
    "attribution": [
        {
            "x": 0,
            "y": 0,
            "w": 40,
            "h": 1,
            "corr": 0.91,
            "x_frac": 0.0,
            "y_frac": 0.0,
            "w_frac": 0.167,
            "h_frac": 1.0,
        }
    ],
    "provenance": {
        "scorer": "bullet-contrast",
        "domain": "striated",
        "input_hashes": {"mark_a": ["<sha256>"], "mark_b": ["<sha256>"]},
    },
    "scope_note": "This is a calibrated weight of evidence on the pooled bullet-land "
    "reference population; it is not a claim about the error rate of "
    "striated examination, which remains unknown.",
    "previews": {"a": "[[…]] downsampled height grids", "b": "[[…]]"},
}


@app.post(
    "/compare",
    tags=["compare"],
    summary="Compare two marks → calibrated likelihood-ratio report",
    responses={200: {"content": {"application/json": {"example": _COMPARE_EXAMPLE}}}},
)
async def compare(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
) -> dict:
    """Compare two marks into a calibrated, bounded **likelihood ratio** with
    region-level attribution. (Lean payload; use `/v1/compare?include=...` for the
    inspectable intermediate computations.)"""
    return await _run_compare(domain, mark_a, mark_b, include=set())


# --- Versioned API (/v1): comparison with inspectable intermediates ---------

v1 = APIRouter(prefix="/v1")


@v1.post(
    "/compare",
    tags=["v1"],
    summary="Compare two marks, optionally returning intermediate computations",
    responses={200: {"content": {"application/json": {"example": _COMPARE_EXAMPLE}}}},
)
async def compare_v1(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
    include: str | None = Form(None),
) -> dict:
    """Same calibrated comparison as `/compare`, plus — on request — the algorithm's
    intermediate computations. `include` is a comma-separated subset of:

    - **calibration** — the reference Tippett curve + KM/KNM score histogram with
      this comparison's score located on it (what makes the LR defensible).
    - **features** — the land×land CCF matrix and the structure features the score
      is built from (`diag_contrast`, `offset_margin`, `lag_coherence`, …).
    - **perland** — per-land evidence on the winning diagonal (diagnostic; lands
      are not independent, so the reportable LR is the aggregate).
    - **trace** — the full signature pipeline (raw → bandpassed → oriented →
      signature) for the best-matching land of each bullet.

    `include=all` returns everything. The response always carries an
    applicability-domain `scope` annotation for the inputs."""
    return await _run_compare(
        domain, mark_a, mark_b, include=parse_include(include) or {"calibration"}
    )


@v1.post("/scope", tags=["v1"], summary="Applicability-domain check for one scan")
async def scope_v1(
    scan: UploadFile = File(...),
    domain: str = Form(...),
    mode: str = Form("warn"),
) -> dict:
    """Check whether one scan is inside the validated domain for `domain`
    (resolution, mark type, coverage, signal). In `mode=refuse` an out-of-domain
    scan is reported `admissible=false` — the basis for refusing a junk LR."""
    if domain not in available_domains():
        raise HTTPException(status_code=400, detail=f"unknown domain {domain!r}")
    surface = await _read_surface(scan)
    return check_applicability(surface, domain=domain, mode=mode).to_dict()


@v1.post(
    "/compare/report.pdf",
    tags=["v1"],
    summary="Court-ready per-comparison PDF report",
    response_class=Response,
)
async def compare_report_pdf(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
    case_id: str | None = Form(None),
    examiner: str | None = Form(None),
) -> Response:
    """Run the comparison and return a court-ready PDF: the calibrated LR with its
    credible interval and verbal weight, the named-scope statement, the reference
    and its cost, the method/pipeline version, the SHA-256 provenance of the input
    scans, and the attribution overlay."""
    report = await _run_compare(domain, mark_a, mark_b, include=set())
    from verity.report_pdf import render_comparison_pdf

    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        render_comparison_pdf(report, path, case_id=case_id, examiner=examiner)
        data = Path(path).read_bytes()
    finally:
        os.remove(path)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=verity-comparison-report.pdf"},
    )


app.include_router(v1)


_SCALAR_HTML = """<!doctype html>
<html>
  <head>
    <title>Verity API reference</title>
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
    """A pretty, modern API reference (Scalar), rendered from the OpenAPI schema.
    Swagger UI (/docs) and ReDoc (/redoc) are also available."""
    return HTMLResponse(_SCALAR_HTML)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/scalar")


def run() -> None:
    import uvicorn

    uvicorn.run("verity_api.main:app", host="127.0.0.1", port=8000, reload=False)
