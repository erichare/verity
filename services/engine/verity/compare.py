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

from .aggregate import bullet_comparison
from .areal import areal_signature
from .cmr import areal_votes, cmr_regions_1d_pair, consensus_members, regions_from_members
from .decision.scorer import BulletScorer, ContrastScorer
from .decision.scorer_config import DEFAULT_SCORER_CONFIG
from .preprocess import isolate_roughness, remove_form
from .region import DEFAULT_KEEP, extract_region
from .registration.align import align_1d
from .report import ComparisonReport, build_comparison_report
from .signature import striation_signature
from .surface import Surface

# Single source of truth for the scorer hyperparameters — bundled with each reference
# and drift-checked at load time (see verity.decision.scorer_config).
_CFG = DEFAULT_SCORER_CONFIG
_LAMBDA_S, _LAMBDA_C = _CFG.lambda_s, _CFG.lambda_c  # striated roughness band (m)
_CMR_CORR, _CMR_TOL = _CFG.cmr_corr, _CFG.cmr_tol  # 2-D CMR congruence thresholds
_CMR_1D_CORR, _CMR_1D_LAG = _CFG.cmr_1d_corr, _CFG.cmr_1d_lag  # 1-D striae-band congruence

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


def _land_fields(surface: Surface) -> tuple[np.ndarray, np.ndarray]:
    """A land's ``(signature, oriented striae band)``. Mirrors
    :func:`striation_signature` exactly (so the score is unchanged) but also returns
    the 2-D oriented+cropped striae field to render the matched striae on."""
    s = remove_form(surface, degree=2)
    s = isolate_roughness(s, _LAMBDA_S, _LAMBDA_C)
    z = s.heights
    w = (~np.isnan(z)).astype(np.float64)
    zr, _wr, prof, (lo, hi), _tilt = extract_region(z, w, keep=DEFAULT_KEEP)
    return prof[lo:hi], zr[:, lo:hi]


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
    cluster_ids: np.ndarray | None = None,
) -> tuple[ComparisonReport, dict]:
    """Compare two surfaces → (report, previews). The report's ``attribution`` holds
    the matched regions (congruent cells for impressed, consecutive matching striae
    for striated) and ``previews`` the two rendered surfaces to overlay them on. The
    striated path here is a *single land* per mark (weakly diagnostic); a full bullet
    uses :func:`compare_bullets_with_previews`."""
    attribution: list[dict] = []
    attribution_b: list[dict] = []
    previews: dict = {}
    if domain == "impressed":
        sig_a, sig_b = areal_signature(surface_a), areal_signature(surface_b)
        members = consensus_members(
            areal_votes(sig_a, sig_b), corr_thresh=_CMR_CORR, transform_tol=_CMR_TOL
        )
        score, score_kind = float(len(members)), "cmr-2d"
        attribution = regions_from_members(members, sig_a.shape)
        attribution_b = regions_from_members(members, sig_b.shape, shift=True)
        previews = {"a": _to_preview(sig_a, preview_size), "b": _to_preview(sig_b, preview_size)}
    elif domain == "striated":
        sig_a, band_a = _land_fields(surface_a)
        sig_b, band_b = _land_fields(surface_b)
        score, score_kind = float(align_1d(sig_a, sig_b)[1]), "ccf"
        attribution, attribution_b = cmr_regions_1d_pair(
            sig_a, sig_b, corr_thresh=_CMR_1D_CORR, lag_tol=_CMR_1D_LAG
        )
        previews = {"a": _to_preview(band_a, preview_size), "b": _to_preview(band_b, preview_size)}
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
        attribution_b=attribution_b,
        provenance={"scorer": score_kind, "domain": domain, **(provenance or {})},
        ci_clusters=cluster_ids,
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
    cluster_ids: np.ndarray | None = None,
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
        cluster_ids=cluster_ids,
    )
    return report


def compare_bullets_with_previews(
    surfaces_a: list[Surface],
    surfaces_b: list[Surface],
    *,
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    reference_name: str,
    provenance: dict | None = None,
    preview_size: int = 140,
    scorer: BulletScorer | None = None,
    cluster_ids: np.ndarray | None = None,
) -> tuple[ComparisonReport, dict]:
    """Compare two *bullets* (each a set of land scans) → ``(report, previews)``.

    A single striated land is only weakly diagnostic; firearms identification gets
    its power from aggregating a bullet's lands. The default ``scorer`` is
    :class:`~verity.decision.scorer.ContrastScorer` (``diag_contrast`` — how far the
    matched land diagonal stands above the rest of the CCF matrix), selected over
    ``diag_mean`` and a multivariate fusion by a barrel-disjoint ablation
    (``verity-margin``). The scorer is pluggable, but a deployment must calibrate
    against a reference scored the same way. For attribution, the strongest-matching
    land of each bullet is rendered, and the **consecutive matching striae** (windows
    agreeing on the common lag) are returned as overlay bands."""
    scorer = scorer or ContrastScorer()
    fields_a = [_land_fields(s) for s in surfaces_a]
    fields_b = [_land_fields(s) for s in surfaces_b]
    sigs_a = [f[0] for f in fields_a]
    sigs_b = [f[0] for f in fields_b]

    cmp = bullet_comparison(sigs_a, sigs_b)
    # diag_contrast (diagonal minus off-diagonal), NOT the raw diagonal mean: KNM
    # bullets get a high diagonal by the luck of the max over cyclic rotations, but
    # their whole matrix is high (flat, low contrast); KM bullets stand *above*
    # their background. The barrel-disjoint ablation (verity-margin) picks this
    # over diag_mean and a multivariate fusion (which ties it / overfits).
    score = float("nan") if cmp is None else scorer.score(cmp)

    attribution: list[dict] = []
    attribution_b: list[dict] = []
    previews: dict = {}
    best: dict = {}
    if cmp is not None:
        i = int(np.argmax(cmp.diag_ccf))  # strongest land of A on the winning diagonal
        j = (i + cmp.offset) % len(sigs_b)  # its partner land in B
        sig_a, band_a = fields_a[i]
        sig_b, band_b = fields_b[j]
        attribution, attribution_b = cmr_regions_1d_pair(
            sig_a, sig_b, corr_thresh=_CMR_1D_CORR, lag_tol=_CMR_1D_LAG
        )
        previews = {"a": _to_preview(band_a, preview_size), "b": _to_preview(band_b, preview_size)}
        best = {"best_land_a": i, "best_land_b": j, "best_land_ccf": float(cmp.diag_ccf[i])}

    report = build_comparison_report(
        score=float(score),
        reference_scores=reference_scores,
        reference_labels=reference_labels,
        domain="striated",
        reference_name=reference_name,
        score_kind=scorer.name,
        attribution=attribution,
        attribution_b=attribution_b,
        provenance={
            "scorer": scorer.name,
            "domain": "striated",
            "n_lands_a": len(sigs_a),
            "n_lands_b": len(sigs_b),
            **best,
            **(provenance or {}),
        },
        ci_clusters=cluster_ids,
    )
    return report, previews


def compare_bullets(
    surfaces_a: list[Surface],
    surfaces_b: list[Surface],
    *,
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    reference_name: str,
    provenance: dict | None = None,
    cluster_ids: np.ndarray | None = None,
) -> ComparisonReport:
    """:func:`compare_bullets_with_previews` without the previews."""
    report, _ = compare_bullets_with_previews(
        surfaces_a,
        surfaces_b,
        reference_scores=reference_scores,
        reference_labels=reference_labels,
        reference_name=reference_name,
        provenance=provenance,
        cluster_ids=cluster_ids,
    )
    return report
