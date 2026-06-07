"""Verity comparison API — serves the calibrated :class:`ComparisonReport`.

``POST /compare`` takes two X3P uploads + a domain, decodes them with the native
``verity_x3p`` codec, runs the domain scorer, calibrates against the bundled
reference, and returns the report JSON. ``GET /health`` lists the calibrated
domains. The decision stays in the engine's bounded-LR firewall; this layer only
decodes, dispatches, and serializes. The Next.js UI renders the response.
"""

from __future__ import annotations

import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import verity_x3p
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from verity.compare import compare_bullets_with_previews, compare_with_previews
from verity.detect import detect_domain
from verity.surface import Surface

from .references import available_domains, load_reference, load_striated_single_land


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
ratio against a named reference population (with a characterized cost, *Cllr*), and
returns region-level **attribution** — the parts of the marks that drove the match.

The decision stays behind a glass-box statistical firewall: the reported LR is a
monotone, bounded transform of the score, interpretable regardless of how the score
was computed. It is *not* a claim about the error rate of forensic examination,
which remains unknown.

Web app: <https://verity.codes> · Method & references: <https://verity.codes/#science>
"""

_TAGS = [
    {"name": "compare", "description": "Compare two marks → a calibrated likelihood-ratio report."},
    {"name": "meta", "description": "Service health and mark-type detection."},
]

app = FastAPI(
    title="Verity comparison API",
    version="0.1.0",
    summary="Calibrated, bounded likelihood ratios for forensic surface comparison.",
    description=_DESCRIPTION,
    contact={"name": "Verity", "url": "https://verity.codes"},
    license_info={"name": "MIT / Apache-2.0"},
    openapi_tags=_TAGS,
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


async def _read_surface(upload: UploadFile) -> Surface:
    data = await upload.read()
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


@app.get("/health", tags=["meta"], summary="Service health + calibrated domains", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok", "engine_version": _engine_version(), "domains": available_domains()}


@app.post("/detect", tags=["meta"], summary="Suggest a mark type from one scan", response_model=DetectResponse)
async def detect(scan: UploadFile = File(...)) -> dict:
    """Suggest a mark type for one uploaded scan, from striation anisotropy — the
    structure-tensor coherence of its 2-D FFT power (directional striae → `striated`;
    isotropic areal → `impressed`). The UI pre-selects it; the user confirms, since
    the mark type picks the calibration reference."""
    surface = await _read_surface(scan)
    domain, coherence = detect_domain(surface)
    return {"domain": domain, "coherence": round(coherence, 3)}


_COMPARE_EXAMPLE = {
    "domain": "striated",
    "score": 0.153,
    "score_kind": "bullet-contrast",
    "likelihood_ratio": 146.0,
    "log10_lr": 2.16,
    "direction": "same source",
    "verbal": "moderately strong support for same source",
    "lr_bound_log10": 2.16,
    "reference": {
        "name": "pooled bullet-land reference (Hamby-252 & 173, Beretta, Phoenix)",
        "n_km": 146, "n_knm": 1755, "cllr": 0.09, "cllr_min": 0.06, "auc": 0.984,
    },
    "attribution": [
        {"x": 0, "y": 0, "w": 40, "h": 1, "corr": 0.91,
         "x_frac": 0.0, "y_frac": 0.0, "w_frac": 0.167, "h_frac": 1.0}
    ],
    "attribution_b": [
        {"x": 2, "y": 0, "w": 40, "h": 1, "corr": 0.91,
         "x_frac": 0.008, "y_frac": 0.0, "w_frac": 0.167, "h_frac": 1.0}
    ],
    "provenance": {"scorer": "bullet-contrast", "domain": "striated",
                   "n_lands_a": 6, "n_lands_b": 6, "best_land_a": 0, "best_land_b": 0},
    "scope_note": "This is a calibrated weight of evidence on the pooled bullet-land "
                  "reference population; it is not a claim about the error rate of "
                  "striated examination, which remains unknown.",
    "previews": {"a": "[[…]] downsampled height grids of the rendered surfaces", "b": "[[…]]"},
}


@app.post(
    "/compare",
    tags=["compare"],
    summary="Compare two marks → calibrated likelihood-ratio report",
    responses={
        200: {
            "description": "Calibrated comparison report (previews are downsampled "
                           "height-grid arrays, elided in this example).",
            "content": {"application/json": {"example": _COMPARE_EXAMPLE}},
        }
    },
)
async def compare(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
) -> dict:
    """Compare two marks into a calibrated, bounded **likelihood ratio** with
    region-level attribution.

    - **striated** — each mark may be a *bullet*: upload all of its land scans
      (e.g. 6). Aggregating the lands is the strong path; a single land per mark is
      weakly diagnostic and is calibrated against a separate single-land reference.
    - **impressed** — one breech-face scan per mark.

    Returns the report plus `previews` (the rendered surfaces) and `attribution` /
    `attribution_b` (the matched regions on Mark A and Mark B)."""
    if domain not in available_domains():
        raise HTTPException(
            status_code=400,
            detail=f"domain {domain!r} has no calibrated reference; available: {available_domains()}",
        )
    if not mark_a or not mark_b:
        raise HTTPException(status_code=400, detail="provide at least one scan per mark")
    scores, labels, reference_name = load_reference(domain)
    provenance = {
        "api_version": app.version,
        "engine_version": _engine_version(),
        "mark_a": [f.filename for f in mark_a],
        "mark_b": [f.filename for f in mark_b],
    }
    if domain == "striated":
        surfaces_a = [await _read_surface(f) for f in mark_a]
        surfaces_b = [await _read_surface(f) for f in mark_b]
        if len(surfaces_a) == 1 and len(surfaces_b) == 1:
            # One land per mark is weakly diagnostic and has no land×land structure —
            # calibrate against the single-land reference, not the bullet reference.
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
        else:
            report, previews = compare_bullets_with_previews(
                surfaces_a,
                surfaces_b,
                reference_scores=scores,
                reference_labels=labels,
                reference_name=reference_name,
                provenance=provenance,
            )
        return {**report.to_dict(), "previews": previews}
    # impressed: a single breech-face scan per mark
    surface_a = await _read_surface(mark_a[0])
    surface_b = await _read_surface(mark_b[0])
    report, previews = compare_with_previews(
        surface_a,
        surface_b,
        domain=domain,
        reference_scores=scores,
        reference_labels=labels,
        reference_name=reference_name,
        provenance=provenance,
    )
    return {**report.to_dict(), "previews": previews}


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
