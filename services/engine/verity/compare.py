"""End-to-end mark-pair comparison — surfaces in, :class:`ComparisonReport` out.

The engine-API entry point. Striated marks (bullet lands, toolmarks) use the 1-D
striation signature + cross-correlation. Impressed marks (breech faces) use the
**Congruent Matching Regions** scorer: the score is the count of congruent regions
and those same regions are returned as **attribution** — the examiner-facing CMS
evidence for *which* parts of the mark drove the match — plus small grayscale
previews to overlay them on. The reference's KM/KNM scores (same scorer) both fit
the bounded calibration and scope it.
"""

from __future__ import annotations

import numpy as np

from .aggregate import bullet_score
from .areal import areal_signature
from .cmr import areal_votes, consensus_members, regions_from_members
from .registration.align import align_1d
from .report import ComparisonReport, build_comparison_report
from .signature import striation_signature
from .surface import Surface

_LAMBDA_S, _LAMBDA_C = 4e-6, 250e-6  # striated roughness band (m)
_CMR_CORR, _CMR_TOL = 0.3, (20.0, 20.0, 6.0)  # CMR congruence thresholds (match the reference)

DOMAINS = ("striated", "impressed")


def _striated_score(surface_a: Surface, surface_b: Surface) -> float:
    sig_a = striation_signature(surface_a, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)
    sig_b = striation_signature(surface_b, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)
    return float(align_1d(sig_a, sig_b)[1])


def _to_preview(sig: np.ndarray, size: int) -> list[list[float]]:
    """Downsample an areal signature to a small [0,1] grayscale grid for overlay."""
    step = max(1, sig.shape[0] // size)
    small = sig[::step, ::step][:size, :size]
    finite = small[np.isfinite(small) & (small != 0.0)]
    if finite.size:
        lo, hi = np.percentile(finite, [2, 98])
        small = np.clip((small - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    return np.nan_to_num(small).round(4).tolist()


def comparison_score(surface_a: Surface, surface_b: Surface, *, domain: str) -> tuple[float, str]:
    """The similarity score for a mark pair and its kind, by domain."""
    if domain == "impressed":
        sig_a, sig_b = areal_signature(surface_a), areal_signature(surface_b)
        members = consensus_members(
            areal_votes(sig_a, sig_b), corr_thresh=_CMR_CORR, transform_tol=_CMR_TOL
        )
        return float(len(members)), "cmr-2d"
    if domain == "striated":
        return _striated_score(surface_a, surface_b), "ccf"
    raise ValueError(f"domain must be one of {DOMAINS}, got {domain!r}")


def compare_with_previews(
    surface_a: Surface,
    surface_b: Surface,
    *,
    domain: str,
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    reference_name: str,
    provenance: dict | None = None,
    preview_size: int = 120,
) -> tuple[ComparisonReport, dict]:
    """Compare two surfaces → (report, previews). For impressed marks the report's
    ``attribution`` holds the congruent matching regions and ``previews`` holds the
    two grayscale signatures to overlay them on (empty for striated, for now)."""
    attribution: list[dict] = []
    previews: dict = {}
    if domain == "impressed":
        sig_a, sig_b = areal_signature(surface_a), areal_signature(surface_b)
        members = consensus_members(
            areal_votes(sig_a, sig_b), corr_thresh=_CMR_CORR, transform_tol=_CMR_TOL
        )
        score, score_kind = float(len(members)), "cmr-2d"
        attribution = regions_from_members(members, sig_a.shape)
        previews = {"a": _to_preview(sig_a, preview_size), "b": _to_preview(sig_b, preview_size)}
    elif domain == "striated":
        score, score_kind = _striated_score(surface_a, surface_b), "ccf"
    else:
        raise ValueError(f"domain must be one of {DOMAINS}, got {domain!r}")

    report = build_comparison_report(
        score=score,
        reference_scores=reference_scores,
        reference_labels=reference_labels,
        domain=domain,
        reference_name=reference_name,
        score_kind=score_kind,
        attribution=attribution,
        provenance={"scorer": score_kind, "domain": domain, **(provenance or {})},
    )
    return report, previews


def compare_surfaces(
    surface_a: Surface,
    surface_b: Surface,
    *,
    domain: str,
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    reference_name: str,
    provenance: dict | None = None,
) -> ComparisonReport:
    """Compare two surfaces into a calibrated :class:`ComparisonReport` (no previews)."""
    report, _ = compare_with_previews(
        surface_a,
        surface_b,
        domain=domain,
        reference_scores=reference_scores,
        reference_labels=reference_labels,
        reference_name=reference_name,
        provenance=provenance,
    )
    return report


def compare_bullets(
    surfaces_a: list[Surface],
    surfaces_b: list[Surface],
    *,
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    reference_name: str,
    provenance: dict | None = None,
) -> ComparisonReport:
    """Compare two *bullets* — each a set of land scans — into a calibrated report.

    A single striated land is only weakly diagnostic; firearms identification gets
    its power from aggregating a bullet's lands. ``bullet_score`` takes the best
    mean land-to-land cross-correlation over cyclic land rotations (the AUC≈1.0
    Phase-1 score), so this is the strong striated path. Calibrated against the
    bullet-level reference (same scorer)."""
    sigs_a = [striation_signature(s, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C) for s in surfaces_a]
    sigs_b = [striation_signature(s, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C) for s in surfaces_b]
    score = bullet_score(sigs_a, sigs_b)
    return build_comparison_report(
        score=float(score),
        reference_scores=reference_scores,
        reference_labels=reference_labels,
        domain="striated",
        reference_name=reference_name,
        score_kind="bullet-ccf",
        provenance={
            "scorer": "bullet-ccf",
            "domain": "striated",
            "n_lands_a": len(sigs_a),
            "n_lands_b": len(sigs_b),
            **(provenance or {}),
        },
    )
