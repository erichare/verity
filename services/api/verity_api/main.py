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

from verity.compare import compare_surfaces
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
    mark_a: UploadFile = File(...),
    mark_b: UploadFile = File(...),
) -> dict:
    if domain not in available_domains():
        raise HTTPException(
            status_code=400,
            detail=f"domain {domain!r} has no calibrated reference; available: {available_domains()}",
        )
    surface_a = await _read_surface(mark_a)
    surface_b = await _read_surface(mark_b)
    scores, labels, reference_name = load_reference(domain)
    report = compare_surfaces(
        surface_a,
        surface_b,
        domain=domain,
        reference_scores=scores,
        reference_labels=labels,
        reference_name=reference_name,
        provenance={"api_version": app.version, "engine_version": _engine_version(),
                    "mark_a": mark_a.filename, "mark_b": mark_b.filename},
    )
    return report.to_dict()


def run() -> None:
    import uvicorn

    uvicorn.run("verity_api.main:app", host="127.0.0.1", port=8000, reload=False)
