"""Best-of-both score fusion — combine complementary similarity scores into one LR.

The global cross-correlation (the whole mark as one region) and the Congruent
Matching Regions count (many local regions) are complementary: global wins when a
mark coheres under a single transform (clean striated), CMR wins when only parts
match (impressed, partial, warped). Rather than choose, fuse them: fit a balanced,
near-unregularized logistic on the stacked score vector and read off the LR. The
calibrator learns to lean on whichever score carries the signal for *this*
reference population, so the fused result is never worse than the better single
score (the weak feature's coefficient can go to zero) and is better where the
scores are complementary.

This is the multivariate sibling of :class:`verity.decision.lr.ScoreLRModel`: same
balanced logistic, same ELUB-style LR bound (so no overstated evidence), same
monotone-in-each-coordinate firewall — just on a feature vector instead of a
scalar. ``cllr_min`` (a 1-D PAV floor) is not defined for a vector, by design:
fusion is a deployable calibration, not a discrimination floor.
"""

from __future__ import annotations

import numpy as np

from .metrics import cllr


class FusionLRModel:
    """Calibrate a vector of per-pair scores to a likelihood ratio.

    Two robustness choices matter when fusing scores on small, source-disjoint
    calibration sets (and they are what keep fusion from underperforming the best
    single score): the features are **standardized** (global correlations and CMR
    counts live on very different scales, which makes an unstandardized logistic
    ill-conditioned), and the fit is **regularized** (``C``) so a weak feature
    cannot overfit on a handful of training sources. ``C=1.0`` is a sensible
    default; the single-feature, near-unregularized case is :class:`ScoreLRModel`.
    """

    def __init__(self, *, lr_bound: str | float | None = "auto", C: float = 1.0) -> None:
        self.lr_bound = lr_bound
        self.C = C
        self._model = None
        self._mean = None
        self._std = None
        self._log_bound: float | None = None

    @staticmethod
    def _as_rows(features: np.ndarray, n: int) -> np.ndarray:
        """Coerce to an ``(n_samples, n_features)`` matrix."""
        x = np.asarray(features, dtype=np.float64)
        if x.ndim == 1:
            x = x[:, None]
        if x.shape[0] != n and x.shape[1] == n:  # given as (n_features, n_samples)
            x = x.T
        return x

    def fit(self, features: np.ndarray, labels: np.ndarray) -> FusionLRModel:
        from sklearn.linear_model import LogisticRegression

        labels = np.asarray(labels, dtype=np.float64)
        x = self._as_rows(features, len(labels))
        self._mean = x.mean(axis=0)
        self._std = x.std(axis=0) + 1e-12
        if self.lr_bound == "auto":
            n_minority = int(min((labels == 1).sum(), (labels == 0).sum()))
            self._log_bound = float(np.log10(max(n_minority, 10)))
        elif self.lr_bound is not None:
            self._log_bound = abs(float(self.lr_bound))
        self._model = LogisticRegression(C=self.C, class_weight="balanced").fit(
            (x - self._mean) / self._std, labels
        )
        return self

    def predict_lr(self, features: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("FusionLRModel must be fit before predict_lr")
        x = np.asarray(features, dtype=np.float64)
        if x.ndim == 1:
            x = x[:, None]
        if x.shape[1] != len(self._mean):
            x = x.T
        p = np.clip(self._model.predict_proba((x - self._mean) / self._std)[:, 1], 1e-4, 1.0 - 1e-4)
        lr = p / (1.0 - p)  # balanced fit -> prior odds 1
        if self._log_bound is not None:
            lr = np.clip(lr, 10.0**-self._log_bound, 10.0**self._log_bound)
        return lr


def fused_cllr(
    feats_train: np.ndarray, y_train: np.ndarray, feats_test: np.ndarray, y_test: np.ndarray
) -> float:
    """Fit fusion on train pairs, score test pairs, return their ``Cllr``."""
    model = FusionLRModel().fit(feats_train, y_train)
    lr = model.predict_lr(feats_test)
    return cllr(lr[y_test == 1], lr[y_test == 0])
