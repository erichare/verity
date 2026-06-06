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

**LR bounding (ELUB-style).** A near-unregularized logistic fit on a *small*
calibration set emits over-confident LRs: on a hard held-out pair a score landing
in the class overlap gets a catastrophically wrong, large-magnitude LR that
dominates ``Cllr``. Following the empirical-bound principle (Vergeer et al. 2016),
``lr_bound`` caps ``|log10 LR|`` at what the reference data can support. The
default ``"auto"`` sets the cap from the rarer class count,
``log10(max(n_minority, 10))`` — you cannot assert evidence stronger than about
``n_same : 1`` from ``n_same`` same-source examples. The cap is monotone, so the
audit-friendly firewall property is preserved, and it is domain-general: it
adapts to each dataset's reference size with no tuning. Barrel-disjoint, this
roughly halves the calibration loss (mean ``Cllr`` 0.44 → 0.28 across the four
bullet studies) while leaving the near-perfectly-discriminated Hamby-252 untouched.
"""

from __future__ import annotations

import numpy as np

from .metrics import cllr

_EPS = 1e-4


class ScoreLRModel:
    """Calibrate scores to likelihood ratios. ``fit`` learns the monotone
    score→posterior map from labelled comparisons; ``predict_lr`` returns the
    prior-independent likelihood ratio, optionally bounded to what the
    calibration set supports (``lr_bound``)."""

    def __init__(self, method: str = "logistic", lr_bound: str | float | None = "auto") -> None:
        if method not in ("logistic", "isotonic"):
            raise ValueError(f"method must be 'logistic' or 'isotonic', got {method!r}")
        if not (lr_bound is None or lr_bound == "auto" or isinstance(lr_bound, int | float)):
            raise ValueError(f"lr_bound must be None, 'auto', or a number, got {lr_bound!r}")
        self.method = method
        self.lr_bound = lr_bound
        self._model = None
        self._prior_odds = 1.0
        self._log_bound: float | None = None

    def _resolve_bound(self, labels: np.ndarray) -> float | None:
        """The ``|log10 LR|`` cap for this fit: explicit float, data-driven
        ``"auto"`` (``log10`` of the rarer class count, floored at 10), or None."""
        if self.lr_bound is None:
            return None
        if self.lr_bound == "auto":
            n_minority = int(min((labels == 1).sum(), (labels == 0).sum()))
            return float(np.log10(max(n_minority, 10)))
        return abs(float(self.lr_bound))

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> ScoreLRModel:
        scores = np.asarray(scores, dtype=np.float64)
        labels = np.asarray(labels, dtype=np.float64)
        prior = float(labels.mean())
        self._prior_odds = prior / (1.0 - prior) if 0.0 < prior < 1.0 else 1.0
        self._log_bound = self._resolve_bound(labels)

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
        """Likelihood ratios for ``scores`` (the prior is divided out), clipped to
        the fitted ``lr_bound`` so no comparison asserts more than the reference
        data can support."""
        if self._model is None:
            raise RuntimeError("ScoreLRModel must be fit before predict_lr")
        posterior = np.clip(self._posterior(scores), _EPS, 1.0 - _EPS)
        lr = (posterior / (1.0 - posterior)) / self._prior_odds
        if self._log_bound is not None:
            lr = np.clip(lr, 10.0**-self._log_bound, 10.0**self._log_bound)
        return lr


def cllr_min(scores: np.ndarray, labels: np.ndarray) -> float:
    """``Cllr`` after PAV-optimal calibration — the discrimination floor (the best
    any monotone calibration of these scores could achieve). Unbounded by
    construction: it is the theoretical floor, not a deployable calibration."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    model = ScoreLRModel(method="isotonic", lr_bound=None).fit(scores, labels)
    lr = model.predict_lr(scores)
    return cllr(lr[labels == 1], lr[labels == 0])
