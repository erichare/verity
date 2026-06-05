"""The transparent calibrated decision layer.

A score (from anything — the Phase-1 cross-correlation today, a learned embedding
similarity later) is turned into a **likelihood ratio** by a *monotone, fitted*
calibration. Because the calibration is a 1-D monotone transform with published
diagnostics, the reported LR is interpretable and auditable no matter how the
score was produced — the firewall that keeps the decision out of the black box.

Two calibrations:

* ``"logistic"`` (default) — a 2-parameter logistic fit (Platt scaling). Robust
  and the right choice for *deployment*, where the calibration must generalize to
  unseen sources.
* ``"isotonic"`` — pool-adjacent-violators. The most flexible monotone fit; used
  for ``cllr_min`` (the best a perfect monotone calibration of *these* scores
  could do), but it overfits when trained on few sources.
"""

from __future__ import annotations

import numpy as np

from .metrics import cllr

_EPS = 1e-4


class ScoreLRModel:
    """Calibrate scores to likelihood ratios. ``fit`` learns the monotone
    score→posterior map from labelled comparisons; ``predict_lr`` returns the
    prior-independent likelihood ratio."""

    def __init__(self, method: str = "logistic") -> None:
        if method not in ("logistic", "isotonic"):
            raise ValueError(f"method must be 'logistic' or 'isotonic', got {method!r}")
        self.method = method
        self._model = None
        self._prior_odds = 1.0

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> ScoreLRModel:
        scores = np.asarray(scores, dtype=np.float64)
        labels = np.asarray(labels, dtype=np.float64)
        prior = float(labels.mean())
        self._prior_odds = prior / (1.0 - prior) if 0.0 < prior < 1.0 else 1.0

        if self.method == "logistic":
            from sklearn.linear_model import LogisticRegression

            # Near-unregularized + balanced classes: the equal-prior Cllr objective
            # wants the calibration slope unshrunk and the minority (KM) class
            # weighted up. ``balanced`` fits as if the prior is 0.5, so the LR is
            # the posterior odds directly (prior_odds set to 1 below).
            self._model = LogisticRegression(C=1e6, class_weight="balanced").fit(
                scores.reshape(-1, 1), labels
            )
            self._prior_odds = 1.0
            return self
        else:
            from sklearn.isotonic import IsotonicRegression

            iso = IsotonicRegression(out_of_bounds="clip", y_min=_EPS, y_max=1.0 - _EPS)
            iso.fit(scores, labels)
            self._model = iso
        return self

    def _posterior(self, scores: np.ndarray) -> np.ndarray:
        scores = np.asarray(scores, dtype=np.float64)
        if self.method == "logistic":
            return self._model.predict_proba(scores.reshape(-1, 1))[:, 1]
        return self._model.predict(scores)

    def predict_lr(self, scores: np.ndarray) -> np.ndarray:
        """Likelihood ratios for ``scores`` (the prior is divided out)."""
        if self._model is None:
            raise RuntimeError("ScoreLRModel must be fit before predict_lr")
        posterior = np.clip(self._posterior(scores), _EPS, 1.0 - _EPS)
        return (posterior / (1.0 - posterior)) / self._prior_odds


def cllr_min(scores: np.ndarray, labels: np.ndarray) -> float:
    """``Cllr`` after PAV-optimal calibration — the discrimination floor (the best
    any monotone calibration of these scores could achieve)."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    model = ScoreLRModel(method="isotonic").fit(scores, labels)
    lr = model.predict_lr(scores)
    return cllr(lr[labels == 1], lr[labels == 0])
