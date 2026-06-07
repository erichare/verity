"""End-to-end mark-pair comparison — surfaces in, :class:`ComparisonReport` out.

The engine-API entry point: take two decoded surfaces and a domain, run the
domain-appropriate scorer, and calibrate the result to a bounded LR against a
named reference population. Striated marks (bullet lands, toolmarks) use the
1-D striation signature + cross-correlation; impressed marks (breech faces) use
the areal signature + 2-D cross-correlation over rotation. The reference's
KM/KNM scores (same scorer) both fit the calibration and scope it.
"""

from __future__ import annotations

import numpy as np

from .areal import areal_score, areal_signature
from .registration.align import align_1d
from .report import ComparisonReport, build_comparison_report
from .signature import striation_signature
from .surface import Surface

_LAMBDA_S, _LAMBDA_C = 4e-6, 250e-6  # striated roughness band (m)

DOMAINS = ("striated", "impressed")


def comparison_score(surface_a: Surface, surface_b: Surface, *, domain: str) -> tuple[float, str]:
    """The similarity score for a mark pair and its kind, by domain."""
    if domain == "impressed":
        return float(areal_score(areal_signature(surface_a), areal_signature(surface_b))), "areal-ccf"
    if domain == "striated":
        sig_a = striation_signature(surface_a, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)
        sig_b = striation_signature(surface_b, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)
        return float(align_1d(sig_a, sig_b)[1]), "ccf"
    raise ValueError(f"domain must be one of {DOMAINS}, got {domain!r}")


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
    """Compare two surfaces into a calibrated :class:`ComparisonReport`."""
    score, score_kind = comparison_score(surface_a, surface_b, domain=domain)
    prov = {"scorer": score_kind, "domain": domain, **(provenance or {})}
    return build_comparison_report(
        score=score,
        reference_scores=reference_scores,
        reference_labels=reference_labels,
        domain=domain,
        reference_name=reference_name,
        score_kind=score_kind,
        provenance=prov,
    )
