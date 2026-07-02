"""Comparison report — the platform's data contract.

Turns one mark-pair comparison into the full reportable payload that the Phase-5
platform serves and renders: the calibrated, ELUB-bounded **likelihood ratio**
with its verbal weight-of-evidence band, the reference-population diagnostics that
*scope* it (``Cllr``/``Cllr_min``/AUC on a named dataset), region-level
**attribution** (the congruent regions that drove the match), **provenance**, and
the honest **scope statement**. Nothing here renders or decides — it assembles a
JSON-serializable structure. The FastAPI endpoint returns it; the Next.js UI
renders it.

The decision stays behind the firewall: the LR comes from the same monotone,
bounded :class:`verity.decision.lr.ScoreLRModel` fit on a named reference
population, so the reported weight of evidence is interpretable regardless of how
the score was computed.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from .decision.lr import ScoreLRModel, cllr_min
from .decision.metrics import cllr, roc_auc
from .decision.uncertainty import lr_credible_interval

# ENFSI-style verbal equivalents, keyed by |log10 LR| (LR 10^k : 1).
_VERBAL_BANDS = (
    (1.0, "weak or limited support"),
    (2.0, "moderate support"),
    (3.0, "moderately strong support"),
    (4.0, "strong support"),
    (6.0, "very strong support"),
    (math.inf, "extremely strong support"),
)


def verbal_weight(log10_lr: float) -> str:
    """ENFSI-style verbal weight of evidence for a log10 LR, with direction."""
    if not math.isfinite(log10_lr) or abs(log10_lr) < 1e-9:
        return "no meaningful support either way"
    magnitude = abs(log10_lr)
    band = next(label for thresh, label in _VERBAL_BANDS if magnitude < thresh)
    direction = "same source" if log10_lr > 0 else "different sources"
    return f"{band} for {direction}"


@dataclass(frozen=True)
class ComparisonReport:
    """The full, JSON-serializable result of one mark-pair comparison."""

    domain: str
    score: float
    score_kind: str  # "ccf" | "cmr" | "fused"
    likelihood_ratio: float
    log10_lr: float
    direction: str  # "same source" | "different sources"
    verbal: str
    lr_bound_log10: float | None  # the ELUB cap applied, if any
    lr_bound_hit: bool  # True when the pre-cap LR exceeded the cap and was clipped to it
    reference: dict  # {name, n_km, n_knm, cllr, cllr_min, auc}
    attribution: list[dict] = field(default_factory=list)  # matched regions on Mark A
    attribution_b: list[dict] = field(default_factory=list)  # the same matches on Mark B
    provenance: dict = field(default_factory=dict)
    scope_note: str = ""
    # Uncertainty on the calibrated LR from bootstrapping the finite reference
    # (None when the interval was not requested). See decision/uncertainty.py.
    log10_lr_ci_lo: float | None = None
    log10_lr_ci_hi: float | None = None
    lr_ci_method: str | None = None
    # Distinct reference sources (barrels/slides) behind a clustered credible interval.
    n_sources: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def build_comparison_report(
    *,
    score: float,
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    domain: str,
    reference_name: str,
    score_kind: str = "cmr",
    attribution: list[dict] | None = None,
    attribution_b: list[dict] | None = None,
    provenance: dict | None = None,
    lr_bound: str | float | None = "auto",
    ci: bool = True,
    ci_n_boot: int | None = None,
    ci_seed: int = 0,
    ci_clusters: np.ndarray | None = None,
) -> ComparisonReport:
    """Calibrate ``score`` to a bounded LR against a named reference population and
    assemble the report. The reference (its KM/KNM scores) both fits the
    score→LR calibration and supplies the diagnostics that scope it.

    When ``ci`` is set, a percentile **credible interval** on ``log10 LR`` is added
    by bootstrapping the reference (see :mod:`verity.decision.uncertainty`); the
    ensemble is memoized per reference, so repeated calls against a bundled
    reference pay the bootstrap cost only once. ``ci_n_boot=None`` resolves
    :func:`verity.decision.uncertainty.default_n_boot` (``VERITY_LR_BOOTSTRAP_N``,
    default 1000). ``ci_clusters`` (the source/barrel of each reference comparison)
    switches it to the honest clustered bootstrap."""
    reference_scores = np.asarray(reference_scores, dtype=np.float64)
    reference_labels = np.asarray(reference_labels, dtype=np.float64)

    model = ScoreLRModel(lr_bound=lr_bound).fit(reference_scores, reference_labels)
    lr_arr, hit_arr = model.predict_lr(np.asarray([score], dtype=np.float64), return_bound_hit=True)
    lr, lr_bound_hit = float(lr_arr[0]), bool(hit_arr[0])
    log10_lr = float(np.log10(lr))

    ci_lo: float | None = None
    ci_hi: float | None = None
    ci_method: str | None = None
    n_sources: int | None = None
    verbal = verbal_weight(log10_lr)
    if ci:
        interval = lr_credible_interval(
            reference_scores,
            reference_labels,
            float(score),
            lr_bound=lr_bound,
            n_boot=ci_n_boot,
            seed=ci_seed,
            cluster_ids=ci_clusters,
            point_log10_lr=log10_lr,
        )
        ci_lo, ci_hi = interval.lo_log10_lr, interval.hi_log10_lr
        ci_method = f"bootstrap-{interval.resample}"
        n_sources = interval.n_sources
        if interval.straddles_zero:
            verbal += " (direction not resolved at the 95% level)"

    ref_lr = model.predict_lr(reference_scores)
    reference = {
        "name": reference_name,
        "n_km": int((reference_labels == 1).sum()),
        "n_knm": int((reference_labels == 0).sum()),
        "cllr": float(cllr(ref_lr[reference_labels == 1], ref_lr[reference_labels == 0])),
        "cllr_min": float(cllr_min(reference_scores, reference_labels)),
        "auc": float(roc_auc(reference_scores, reference_labels)),
    }
    scope_note = (
        f"This is a calibrated weight of evidence on the {reference_name} reference "
        "population. It is not a verdict: it is one input to an examiner's judgment, "
        f"alongside case context. It is not a claim about the error rate of {domain} "
        "examination, which remains unknown."
    )
    if lr_bound_hit:
        scope_note += (
            " The reported LR is bound-limited: the calibrated value exceeded the "
            "empirical bound this reference can support and was capped at it."
        )
    return ComparisonReport(
        domain=domain,
        score=float(score),
        score_kind=score_kind,
        likelihood_ratio=lr,
        log10_lr=log10_lr,
        direction="same source" if log10_lr > 0 else "different sources",
        verbal=verbal,
        lr_bound_log10=model._log_bound,
        lr_bound_hit=lr_bound_hit,
        reference=reference,
        attribution=list(attribution or []),
        attribution_b=list(attribution_b or []),
        provenance=dict(provenance or {}),
        scope_note=scope_note,
        log10_lr_ci_lo=ci_lo,
        log10_lr_ci_hi=ci_hi,
        lr_ci_method=ci_method,
        n_sources=n_sources,
    )
