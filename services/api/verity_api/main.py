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

from verity.compare import compare_bullets_with_previews, compare_with_previews
from verity.surface import Surface

from .references import available_domains, load_reference


def _engine_version() -> str:
    try:
        return version("verity")
    except PackageNotFoundError:
        return "unknown"


app = FastAPI(
    title="Verity comparison API",
    version="0.1.0",
    summary="Calibrated, bounded likelihood ratios for forensic surface comparison.",
)

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


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": _engine_version(), "domains": available_domains()}


@app.post("/compare")
async def compare(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
) -> dict:
    """Compare two marks. For ``striated`` each mark may be a *bullet* — several
    land scans aggregated (the strong path); for ``impressed`` each is one
    breech-face scan."""
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


def run() -> None:
    import uvicorn

    uvicorn.run("verity_api.main:app", host="127.0.0.1", port=8000, reload=False)
