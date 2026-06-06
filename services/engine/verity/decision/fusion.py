"""Land-level likelihood-ratio fusion.

The Phase-1 bullet score is the *mean* CCF along the matched diagonal — six land
comparisons collapsed to their average. Averaging compresses: a genuine
same-source bullet whose six lands each match moderately ends up with one
middling number, indistinguishable from a different-source bullet that lucked
into the same average.

The forensically correct combination of several pieces of evidence is to convert
each to a likelihood ratio and (under conditional independence given the source)
**multiply** them — i.e. sum the log-LRs. Six concordant land matches then
*accumulate* into a decisive bullet-level weight of evidence, while six lucky-max
noise correlations, each near LR 1, sum to nearly nothing. That spreads the KM
and KNM distributions far apart — the margin this work is after — and the
per-land calibrator is a monotone :class:`ScoreLRModel`, so the audit firewall is
preserved (no black box enters the decision).

Lands are not perfectly independent (subclass and manufacturing effects correlate
them), so the summed log-LR is best treated as a *score* and passed through a
final bullet-level monotone calibration before it is reported as an LR — exactly
how the Phase-1 mean-CCF score is already calibrated. This module produces that
fused score; the validation harness handles the bullet-level calibration and the
barrel-disjoint evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .lr import ScoreLRModel


@dataclass(frozen=True)
class LandFusionModel:
    """Calibrate a single land-pair CCF to a likelihood ratio, then fuse a
    bullet's lands by summing their log-LRs.

    Fit on the diagonal land CCFs of *training* bullet pairs (each land inherits
    its bullet pair's KM/KNM label); apply to held-out pairs. Keeping fit/apply
    separate is what makes the barrel-disjoint evaluation honest."""

    calibrator: ScoreLRModel

    @classmethod
    def fit(
        cls,
        diag_ccfs: list[np.ndarray],
        labels: np.ndarray,
        *,
        method: str = "logistic",
        lr_bound: str | float | None = "auto",
    ) -> LandFusionModel:
        """Fit the per-land CCF→LR calibrator. ``diag_ccfs[k]`` are the matched-
        diagonal land CCFs of bullet pair ``k`` (label ``labels[k]``); every land
        of a pair takes the pair's label.

        ``method`` is the land calibrator: ``"logistic"`` makes ``log LR`` linear
        in the CCF, so the fused (summed) score is affine-equivalent to the mean
        CCF except where the LR bound clips — i.e. it can only widen the margin
        through the bound. ``"isotonic"`` is nonlinear, letting concordant lands
        accumulate genuinely (at the cost of more variance on small reference
        sets)."""
        flat_ccf: list[float] = []
        flat_lab: list[float] = []
        for ccfs, lab in zip(diag_ccfs, np.asarray(labels), strict=True):
            ccfs = np.asarray(ccfs, dtype=np.float64)
            flat_ccf.extend(ccfs.tolist())
            flat_lab.extend([float(lab)] * ccfs.size)
        cal = ScoreLRModel(method=method, lr_bound=lr_bound).fit(
            np.asarray(flat_ccf), np.asarray(flat_lab)
        )
        return cls(calibrator=cal)

    def fused_score(self, diag_ccf: np.ndarray) -> float:
        """Sum of ``log10`` land LRs for one bullet pair — the fused score. Higher
        ⇒ more, and more concordant, land-level evidence for same source."""
        lrs = self.calibrator.predict_lr(np.asarray(diag_ccf, dtype=np.float64))
        return float(np.sum(np.log10(lrs)))

    def fused_scores(self, diag_ccfs: list[np.ndarray]) -> np.ndarray:
        """Fused score for each bullet pair in ``diag_ccfs``."""
        return np.array([self.fused_score(d) for d in diag_ccfs])
