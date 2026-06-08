"""Pluggable bullet scorers — the scalar a bullet-pair comparison collapses to,
before the firewall calibrates it to a likelihood ratio.

The production score is ``diag_contrast`` (how far the matched land diagonal
stands above the rest of the CCF matrix), selected over the Phase-1 ``diag_mean``
and the other structure levers by a **barrel-disjoint ablation**
(``verity-margin`` / :mod:`verity.examples.margin_levers`). Making the scorer a
small protocol keeps that choice explicit and lets a deployment opt into a
multivariate fusion without touching the calibration firewall: a scorer only
produces a *score*; :func:`verity.report.build_comparison_report` still applies
the monotone, ELUB-bounded score→LR map.

``FusionScorer`` combines several structure features (a standardized, lightly
regularized logistic — two-to-three inspectable coefficients, not a black box).
Deploying it requires a reference of fitted comparisons rather than a vector of
scalar scores, so it is offered as an opt-in / research path; ``ContrastScorer``
is the default and leaves behaviour unchanged.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ..aggregate import BulletComparison

DEFAULT_FUSION_FEATURES = ("diag_mean", "diag_contrast", "lag_coherence")


@runtime_checkable
class BulletScorer(Protocol):
    """A scalar score for a bullet-pair comparison (higher = more same-source)."""

    name: str

    def score(self, comparison: BulletComparison) -> float: ...


class ContrastScorer:
    """The production scorer: ``diag_contrast``. Selected by the barrel-disjoint
    lever ablation; leaves the deployed behaviour unchanged."""

    name = "bullet-contrast"

    def score(self, comparison: BulletComparison) -> float:
        return float(comparison.diag_contrast)


class FusionScorer:
    """A transparent multivariate fusion of CCF-matrix structure features.

    Fit on labelled comparisons; the score is the standardized logistic's
    decision function (the logit). The handful of coefficients are inspectable
    (see :attr:`coefficients`), and the final score→LR calibration still happens
    behind the firewall, so the glass-box property is preserved."""

    name = "bullet-fusion"

    def __init__(self, clf, scaler, features: tuple[str, ...]) -> None:
        self._clf = clf
        self._scaler = scaler
        self._features = features

    @classmethod
    def fit(
        cls,
        comparisons: list[BulletComparison],
        labels: np.ndarray,
        *,
        features: tuple[str, ...] = DEFAULT_FUSION_FEATURES,
        C: float = 1.0,
    ) -> FusionScorer:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        x = np.array([[c.features()[f] for f in features] for c in comparisons], dtype=np.float64)
        labels = np.asarray(labels, dtype=np.float64)
        scaler = StandardScaler().fit(x)
        clf = LogisticRegression(C=C, class_weight="balanced").fit(scaler.transform(x), labels)
        return cls(clf, scaler, tuple(features))

    def score(self, comparison: BulletComparison) -> float:
        feats = comparison.features()
        x = self._scaler.transform([[feats[f] for f in self._features]])
        return float(self._clf.decision_function(x)[0])

    @property
    def coefficients(self) -> dict[str, float]:
        """The fitted (standardized) weight per feature — the glass-box audit of
        what the fusion is using."""
        return dict(zip(self._features, self._clf.coef_[0].tolist(), strict=True))
