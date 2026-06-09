"""Serialize the algorithm's intermediate computations for the API.

The default ``/compare`` returns the final calibrated LR. These helpers expose the
*work behind it* on request (``include=...``) — the reference calibration curve
with this comparison's score on it, the CCF-matrix structure features the score is
built from, per-land evidence, and the full pipeline trace for the matched lands —
so the result is inspectable end to end, not a black box. Arrays are downsampled
to keep payloads bounded; scalars are exact.
"""

from __future__ import annotations

import numpy as np

from verity import land_trace
from verity.aggregate import bullet_comparison
from verity.decision import DEFAULT_SCORER_CONFIG, ScoreLRModel, eer, roc_auc, tippett
from verity.surface import Surface
from verity.trace import LandTrace

_LAMBDA_S, _LAMBDA_C = DEFAULT_SCORER_CONFIG.lambda_s, DEFAULT_SCORER_CONFIG.lambda_c
# "recipe" is the reproducible methods-as-JSON + content handle (see recipe.py); it is
# assembled in main.py rather than here, but shares the include selector.
VALID_INCLUDES = frozenset({"calibration", "features", "perland", "trace", "recipe"})


def parse_include(raw: str | None) -> set[str]:
    """Parse a comma-separated ``include`` selector. ``all`` expands to everything;
    unknown tokens are ignored."""
    if not raw:
        return set()
    tokens = {t.strip().lower() for t in raw.split(",") if t.strip()}
    if "all" in tokens:
        return set(VALID_INCLUDES)
    return tokens & VALID_INCLUDES


def _decimate_1d(arr: np.ndarray, max_len: int = 512) -> list[float]:
    arr = np.asarray(arr, dtype=np.float64)
    if arr.size > max_len:
        step = arr.size // max_len + 1
        arr = arr[::step]
    return np.nan_to_num(arr).round(5).tolist()


def _downsample_grid(arr: np.ndarray, size: int = 120) -> list[list[float]]:
    a = np.asarray(arr, dtype=np.float64)
    step = max(1, max(a.shape) // size)
    small = a[::step, ::step][:size, :size]
    finite = small[np.isfinite(small) & (small != 0.0)]
    if finite.size:
        lo, hi = np.percentile(finite, [2, 98])
        small = np.clip((small - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    return np.nan_to_num(small).round(4).tolist()


def calibration_diagnostics(
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    score: float,
    reference_name: str,
    *,
    lr_bound: str | float | None = "auto",
    n_bins: int = 24,
) -> dict:
    """The reference calibration, with this comparison's score located on it: the
    Tippett curve, the KM/KNM score histogram, and the calibration scalars. This is
    the figure that makes the reported LR defensible to a statistician."""
    scores = np.asarray(reference_scores, dtype=np.float64)
    labels = np.asarray(reference_labels, dtype=np.float64)
    model = ScoreLRModel(lr_bound=lr_bound).fit(scores, labels)
    ref_lr = model.predict_lr(scores)
    km_lr, knm_lr = ref_lr[labels == 1], ref_lr[labels == 0]
    thr, km_ge, knm_ge = tippett(km_lr, knm_lr)
    this_lr = float(model.predict_lr(np.asarray([score], dtype=np.float64))[0])

    edges = np.linspace(float(scores.min()), float(scores.max()), n_bins + 1)
    km_counts, _ = np.histogram(scores[labels == 1], bins=edges)
    knm_counts, _ = np.histogram(scores[labels == 0], bins=edges)
    return {
        "reference_name": reference_name,
        "n_km": int((labels == 1).sum()),
        "n_knm": int((labels == 0).sum()),
        "auc": float(roc_auc(scores, labels)),
        "eer": float(eer(scores, labels)),
        "lr_bound_log10": model._log_bound,
        "score_marker": float(score),
        "this_log10_lr": float(np.log10(this_lr)),
        "km_knm_hist": {
            "edges": edges.round(5).tolist(),
            "km_counts": km_counts.tolist(),
            "knm_counts": knm_counts.tolist(),
        },
        "tippett": {
            "log10_lr": np.log10(thr).round(4).tolist(),
            "km_ge": km_ge.round(4).tolist(),
            "knm_ge": knm_ge.round(4).tolist(),
        },
    }


def trace_dict(trace: LandTrace, *, grid: int = 120, sig_max: int = 512) -> dict:
    """A :class:`LandTrace` as JSON: scalar angles/crop exact, 2-D stages
    downsampled to a small grid, the signature decimated."""
    return {
        "tilt_deg": round(float(trace.tilt_deg), 3),
        "striae_angle_deg": round(float(trace.striae_angle_deg), 3),
        "crop": [int(trace.crop[0]), int(trace.crop[1])],
        "dx_um": round(float(trace.dx) * 1e6, 4),
        "dy_um": round(float(trace.dy) * 1e6, 4),
        "shape_raw": [int(trace.raw.shape[0]), int(trace.raw.shape[1])],
        "raw_preview": _downsample_grid(trace.raw, grid),
        "bandpassed_preview": _downsample_grid(trace.bandpassed, grid),
        "rotated_preview": _downsample_grid(trace.rotated, grid),
        "signature": _decimate_1d(trace.signature, sig_max),
        "downsample": {"grid": grid, "signature_max": sig_max},
    }


def bullet_features_dict(cmp) -> dict:
    """The CCF-matrix structure features + the land×land matrix, as JSON. The single
    serializer shared by ``include=features`` and the ``/v1/steps/features`` endpoint, so
    the inline and addressable views are byte-identical."""
    i = int(np.argmax(cmp.diag_ccf))
    j = (i + cmp.offset) % cmp.ccf.shape[1]
    return {
        **{k: round(float(v), 5) for k, v in cmp.features().items()},
        "offset": int(cmp.offset),
        "diag_ccf": cmp.diag_ccf.round(5).tolist(),
        "land_ccf_matrix": np.round(cmp.ccf, 5).tolist(),  # bullets have few lands → small
        "best_land_a": i,
        "best_land_b": j,
    }


def striated_bullet_intermediates(
    surfaces_a: list[Surface],
    surfaces_b: list[Surface],
    include: set[str],
    *,
    single_land_reference: tuple[np.ndarray, np.ndarray, str] | None = None,
) -> dict:
    """Intermediates for a bullet pair: structure features + the land×land CCF
    matrix (``features``), per-land evidence on the winning diagonal (``perland``,
    diagnostic — not the reportable aggregate), and the full pipeline trace for the
    best-matching land of each bullet (``trace``)."""
    if not (include & {"features", "perland", "trace"}):
        return {}
    traces_a = [land_trace(s, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C) for s in surfaces_a]
    traces_b = [land_trace(s, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C) for s in surfaces_b]
    sigs_a = [t.signature for t in traces_a]
    sigs_b = [t.signature for t in traces_b]
    cmp = bullet_comparison(sigs_a, sigs_b)
    if cmp is None:
        return {}
    i = int(np.argmax(cmp.diag_ccf))
    j = (i + cmp.offset) % len(sigs_b)
    out: dict = {}

    if "features" in include:
        out["features"] = bullet_features_dict(cmp)

    if "perland" in include and single_land_reference is not None:
        s_scores, s_labels, s_name = single_land_reference
        model = ScoreLRModel().fit(
            np.asarray(s_scores, dtype=np.float64), np.asarray(s_labels, dtype=np.float64)
        )
        lands = []
        for k in range(len(sigs_a)):
            ccf = float(cmp.diag_ccf[k])
            land_lr = float(model.predict_lr(np.asarray([ccf], dtype=np.float64))[0])
            lands.append(
                {
                    "a": k,
                    "b": (k + cmp.offset) % len(sigs_b),
                    "ccf": round(ccf, 5),
                    "lag": int(cmp.diag_lags[k]),
                    "land_lr": round(land_lr, 4),
                    "land_log10_lr": round(float(np.log10(land_lr)), 4),
                }
            )
        out["per_land"] = {
            "offset": int(cmp.offset),
            "lands": lands,
            "single_land_reference": s_name,
            "note": "Per-land LRs are diagnostic; lands are not independent, so the "
            "reportable bullet LR is the aggregate, not their product.",
        }

    if "trace" in include:
        out["trace"] = {"a": trace_dict(traces_a[i]), "b": trace_dict(traces_b[j])}

    return out
