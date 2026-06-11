"""Glass-box step endpoints: every pipeline stage, independently addressable.

Each step wraps an engine function 1:1, takes its inputs as content handles, and returns
the output artifact's handle + provenance — reusing the same serializers as ``include=``
so a standalone step can't drift from the inline view. First ``POST /v1/artifacts`` a
scan for a surface handle, then chain steps by handle: the result is a content-addressed
DAG from scan to score, every intermediate fetchable and citable.

Compute steps are sync ``def`` handlers, so FastAPI runs them in its worker threadpool
off the event loop; their inputs are surfaces already size-capped at upload.
"""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from verity import align_1d, land_trace
from verity.aggregate import bullet_comparison
from verity.areal import areal_signature
from verity.decision import DEFAULT_SCORER_CONFIG, ScoreLRModel
from verity.decision.uncertainty import lr_credible_interval
from verity.preprocess.filters import isolate_roughness
from verity.preprocess.form import remove_form
from verity.report import verbal_weight
from verity.surface import Surface

from . import limits
from .artifacts import STORE, _sha256
from .decode import engine_version, surface_from_bytes
from .intermediates import (
    _decimate_1d,
    _downsample_grid,
    bullet_features_dict,
    calibration_diagnostics,
    trace_dict,
)
from .references import load_reference_by_id

steps = APIRouter(prefix="/v1")

_LAMBDA_S, _LAMBDA_C = DEFAULT_SCORER_CONFIG.lambda_s, DEFAULT_SCORER_CONFIG.lambda_c


def _artifact_or_404(handle: str):
    art = STORE.get(handle)
    if art is None:
        raise HTTPException(
            status_code=404, detail=f"unknown artifact {handle!r} (expired or never created)"
        )
    return art


def _surface_or_400(handle: str) -> Surface:
    surface = STORE.surface(handle)
    if surface is None:
        art = _artifact_or_404(handle)  # raises 404 if truly absent
        raise HTTPException(
            status_code=400, detail=f"artifact {handle} is {art.kind!r}, not a surface"
        )
    return surface


def _signature_1d_or_400(handle: str):
    art = _artifact_or_404(handle)
    if art.kind != "signature.1d":
        raise HTTPException(
            status_code=400, detail=f"artifact {handle} is {art.kind!r}, expected signature.1d"
        )
    return STORE.array(handle)


def _handle_list(raw: str) -> list[str]:
    return [h.strip() for h in raw.split(",") if h.strip()]


# --- the artifact store -----------------------------------------------------


@steps.post("/artifacts", tags=["v1"], summary="Upload a scan → a content-addressed surface handle")
async def put_artifact(scan: UploadFile = File(...)) -> dict:
    """Decode an X3P upload into a surface and store it, returning its content handle.
    The handle is the entry point to the step graph: pass it to `/v1/steps/*`."""
    budget = limits.ByteBudget(limits.LIMITS.max_total_bytes)
    data = await limits.read_capped(scan, file_cap=limits.LIMITS.max_file_bytes, budget=budget)
    limits.validate_x3p(data, filename=scan.filename or "")
    surface = surface_from_bytes(data)
    art = STORE.put_array(
        surface.heights,
        kind="surface",
        meta={
            "dx": surface.dx,
            "dy": surface.dy,
            "shape": list(surface.heights.shape),
            "source_sha256": _sha256(data),
            "filename": scan.filename,
        },
        produced_by={
            "step": "artifacts",
            "code": "verity_x3p.read_x3p",
            "params": {},
            "inputs": [],
            "engine_version": engine_version(),
        },
    )
    return art.summary()


@steps.get("/artifacts/{handle}", tags=["v1"], summary="Artifact record (kind + provenance)")
def get_artifact(handle: str) -> dict:
    return _artifact_or_404(handle).summary()


@steps.get("/artifacts/{handle}/data", tags=["v1"], summary="Raw artifact bytes (.npy)")
def get_artifact_data(handle: str) -> Response:
    """The artifact's array as a NumPy ``.npy`` (load with ``numpy.load``). ETag is the
    content handle, so it is cacheable and self-verifying."""
    art = _artifact_or_404(handle)
    return Response(
        content=art.data,
        media_type="application/octet-stream",
        headers={
            "ETag": art.handle,
            "Content-Disposition": f'attachment; filename="{art.kind}.npy"',
        },
    )


@steps.get("/artifacts/{handle}/preview", tags=["v1"], summary="Downsampled artifact preview")
def get_artifact_preview(handle: str) -> dict:
    """A bounded, JSON-friendly view of the artifact: a decimated 1-D signature or a
    downsampled 2-D grid (the full array is at `/data`)."""
    art = _artifact_or_404(handle)
    arr = STORE.array(handle)
    body = {"handle": art.handle, "kind": art.kind}
    if arr.ndim == 1:
        body["signature"] = _decimate_1d(arr)
    else:
        body["grid"] = _downsample_grid(arr)
    return body


# --- the steps --------------------------------------------------------------


@steps.post("/steps/preprocess", tags=["v1"], summary="Form removal + roughness-band isolation")
def step_preprocess(
    surface: str = Form(...),
    lambda_s: float = Form(_LAMBDA_S),
    lambda_c: float = Form(_LAMBDA_C),
) -> dict:
    """ISO 25178 form removal (degree-2) + ISO 16610 roughness-band isolation → a
    bandpassed surface handle. The cutoffs are exposed for inspection; the deployed
    defaults are the calibrated values."""
    s = _surface_or_400(surface)
    if not lambda_s < lambda_c:
        raise HTTPException(status_code=400, detail="require lambda_s < lambda_c")
    out = isolate_roughness(remove_form(s, degree=2), lambda_s, lambda_c)
    art = STORE.put_array(
        out.heights,
        kind="surface.bandpassed",
        meta={"dx": out.dx, "dy": out.dy, "shape": list(out.heights.shape)},
        produced_by={
            "step": "preprocess",
            "code": "verity.preprocess (remove_form + isolate_roughness)",
            "params": {"form_degree": 2, "lambda_s": lambda_s, "lambda_c": lambda_c},
            "inputs": [surface],
            "engine_version": engine_version(),
        },
    )
    return {**art.summary(), "preview": {"grid": _downsample_grid(out.heights)}}


@steps.post(
    "/steps/signature", tags=["v1"], summary="Striated 1-D signature (the comparison object)"
)
def step_signature(surface: str = Form(...)) -> dict:
    """The full striated pipeline for one land — form removal, roughness isolation,
    FFT orientation, groove crop — to the 1-D across-striae signature. The `preview` is
    byte-identical to `include=trace` (it goes through the same `land_trace`)."""
    s = _surface_or_400(surface)
    trace = land_trace(s, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)
    art = STORE.put_array(
        trace.signature,
        kind="signature.1d",
        meta={
            "length": int(trace.signature.size),
            "tilt_deg": round(float(trace.tilt_deg), 3),
            "striae_angle_deg": round(float(trace.striae_angle_deg), 3),
        },
        produced_by={
            "step": "signature",
            "code": "verity.signature.striation_signature (via land_trace)",
            "params": {"lambda_s": _LAMBDA_S, "lambda_c": _LAMBDA_C, "orient": True, "keep": 0.5},
            "inputs": [surface],
            "engine_version": engine_version(),
        },
    )
    return {**art.summary(), "preview": trace_dict(trace)}


@steps.post("/steps/areal-signature", tags=["v1"], summary="Impressed 2-D areal signature")
def step_areal_signature(surface: str = Form(...)) -> dict:
    """The impressed pipeline for one breech face → the fixed-size, unit-norm areal
    roughness map (the comparison object for the 2-D / CMR path)."""
    s = _surface_or_400(surface)
    sig = areal_signature(s, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)
    art = STORE.put_array(
        sig,
        kind="signature.2d",
        meta={"shape": list(sig.shape)},
        produced_by={
            "step": "areal-signature",
            "code": "verity.areal.areal_signature",
            "params": {"lambda_s": _LAMBDA_S, "lambda_c": _LAMBDA_C, "decimate": 5, "size": 256},
            "inputs": [surface],
            "engine_version": engine_version(),
        },
    )
    return {**art.summary(), "preview": {"grid": _downsample_grid(sig)}}


@steps.post("/steps/align", tags=["v1"], summary="1-D alignment of two signatures (lag + CCF)")
def step_align(a: str = Form(...), b: str = Form(...)) -> dict:
    """Peak normalized cross-correlation of two 1-D signatures over integer lags — the
    pairwise comparison primitive. Returns the best lag and the CCF at it."""
    sig_a, sig_b = _signature_1d_or_400(a), _signature_1d_or_400(b)
    lag, ccf = align_1d(sig_a, sig_b)
    return {
        "step": "align",
        "code": "verity.registration.align.align_1d",
        "inputs": [a, b],
        "lag": int(lag),
        "ccf": round(float(ccf), 6),
        "engine_version": engine_version(),
    }


@steps.post(
    "/steps/features", tags=["v1"], summary="Bullet land×land CCF matrix + structure features"
)
def step_features(a: str = Form(...), b: str = Form(...)) -> dict:
    """Compare two bullets' lands (comma-separated `signature.1d` handles per side) into
    the land×land CCF matrix and the structure features the score is built from
    (`diag_contrast`, `offset_margin`, `lag_coherence`, …). Identical serialization to
    `include=features`."""
    handles_a, handles_b = _handle_list(a), _handle_list(b)
    if not handles_a or not handles_b:
        raise HTTPException(status_code=400, detail="provide ≥1 signature.1d handle per side")
    sigs_a = [_signature_1d_or_400(h) for h in handles_a]
    sigs_b = [_signature_1d_or_400(h) for h in handles_b]
    cmp = bullet_comparison(sigs_a, sigs_b)
    if cmp is None:
        raise HTTPException(status_code=400, detail="could not form a land×land comparison")
    return {
        "step": "features",
        "code": "verity.aggregate.bullet_comparison",
        "inputs": {"a": handles_a, "b": handles_b},
        "features": bullet_features_dict(cmp),
        "engine_version": engine_version(),
    }


_CALIBRATE_REASON = (
    "Refused to emit a calibrated LR: the score was computed under scorer config {got}, "
    "but reference {ref!r} is calibrated under {want}. The two scores live on different "
    "scales, so a calibrated LR would be meaningless rather than merely uncertain. Score "
    "under the reference's config, or calibrate against a reference built under {got}."
)


@steps.post(
    "/steps/calibrate", tags=["v1"], summary="Calibrate a score → bounded LR (the firewall)"
)
def step_calibrate(
    score: float = Form(...),
    reference: str = Form(...),
    scorer_config_hash: str | None = Form(None),
    ci: bool = Form(True),
) -> dict:
    """Map a comparison score to a bounded likelihood ratio against a named reference —
    the calibration firewall, as an addressable step. The reference (its KM/KNM scores)
    both fits the monotone, ELUB-bounded calibration and scopes it.

    The firewall: a calibrated LR is valid only if the score was produced under the
    *same* scorer config as the reference. If the caller declares a `scorer_config_hash`
    that does **not** match the reference's, the LR is **refused** (`calibrated: false`,
    raw score passed through) — a mis-scaled number would be worse than none. If the hash
    matches, the LR is emitted with `config_verified: true`; if omitted, the LR is emitted
    with `config_verified: false` (the deployed pipeline uses the matching config, so the
    common case is sound, but the caller hasn't proven it). The bullet score to pass here
    is `features.diag_contrast`; the impressed score is the CMR-2D count."""
    try:
        bundle = load_reference_by_id(reference)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown reference {reference!r}") from exc

    ref_hash = bundle.scorer_config_hash
    if scorer_config_hash and ref_hash and scorer_config_hash != ref_hash:
        return {
            "calibrated": False,
            "score": score,
            "reference": reference,
            "requested_scorer_config_hash": scorer_config_hash,
            "reference_scorer_config_hash": ref_hash,
            "reason": _CALIBRATE_REASON.format(
                got=scorer_config_hash[:12], ref=reference, want=ref_hash[:12]
            ),
        }

    scores = np.asarray(bundle.scores, dtype=np.float64)
    labels = np.asarray(bundle.labels, dtype=np.float64)
    model = ScoreLRModel(lr_bound="auto").fit(scores, labels)
    lr_arr, hit_arr = model.predict_lr(np.asarray([score], dtype=np.float64), return_bound_hit=True)
    lr = float(lr_arr[0])
    log10_lr = float(np.log10(lr))
    out: dict = {
        "calibrated": True,
        "config_verified": bool(scorer_config_hash and ref_hash and scorer_config_hash == ref_hash),
        "score": score,
        "likelihood_ratio": lr,
        "log10_lr": log10_lr,
        "lr_bound_log10": model._log_bound,
        "lr_bound_hit": bool(hit_arr[0]),
        "direction": "same source" if log10_lr > 0 else "different sources",
        "verbal": verbal_weight(log10_lr),
        "reference": {
            "id": reference,
            "name": bundle.name,
            "scorer_config_hash": ref_hash,
            "diagnostics": (bundle.provenance or {}).get("diagnostics"),
        },
        "calibration": calibration_diagnostics(scores, labels, score, bundle.name),
    }
    if ci:
        interval = lr_credible_interval(
            scores,
            labels,
            float(score),
            lr_bound="auto",
            n_boot=1000,
            seed=0,
            cluster_ids=bundle.cluster_ids,
            point_log10_lr=log10_lr,
        )
        out["log10_lr_ci"] = [interval.lo_log10_lr, interval.hi_log10_lr]
        out["lr_ci_method"] = f"bootstrap-{interval.resample}"
        out["n_sources"] = interval.n_sources
    return out
