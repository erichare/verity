"""Uncertainty on the calibrated likelihood ratio.

The reported LR is calibrated against a *finite* reference population, so the
score→LR map is itself an estimate. A point LR hides that. This module reports a
**credible interval on log10 LR** by resampling the reference and refitting the
**same** monotone, bounded :class:`~verity.decision.lr.ScoreLRModel` in every
replicate — so the audit-firewall property (LR is a monotone, ELUB-bounded
transform of the score) holds for every draw, and the interval inherits it.

Two resampling schemes:

* **row-stratified** (default) — resample within KM and within KNM separately.
  Keeps the class sizes fixed, so the ELUB bound ``log10(max(n_minority, 10))``
  is constant across replicates and the interval reflects *calibration* noise,
  not class-ratio noise. Works with today's bundled references (scores + labels).
* **clustered** (block bootstrap) — when ``cluster_ids`` (e.g. the source/barrel
  of each comparison) is given, resample whole clusters. This is the honest
  version: lands/pairs from one barrel are correlated, so a row bootstrap
  understates the variance. Used once references carry a source column.

The interval is a **percentile** interval: the LR distribution is asymmetric and
piles at the ELUB cap, so a symmetric ±z·SE would misreport the cap. The point
estimate is the full-reference LR (not the bootstrap mean), which avoids
resampling bias on the reported number.

Building the bootstrap ensemble is the expensive step; :class:`BootstrapCalibration`
holds the refit models so one ensemble answers intervals for any query score, and
:func:`cached_bootstrap_calibration` memoizes the ensemble per reference + params
so a server pays the cost once.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

from .lr import ScoreLRModel

__all__ = [
    "LRInterval",
    "BootstrapCalibration",
    "cached_bootstrap_calibration",
    "lr_credible_interval",
]


@dataclass(frozen=True)
class LRInterval:
    """A credible interval on the calibrated ``log10`` likelihood ratio."""

    point_log10_lr: float
    lo_log10_lr: float
    hi_log10_lr: float
    alpha: float
    n_boot: int  # replicates that fit (degenerate clustered draws are skipped)
    method: str  # the calibration method ("logistic" | "isotonic")
    resample: str  # "row-stratified" | "clustered"
    n_sources: int | None  # number of clusters, when clustered

    @property
    def straddles_zero(self) -> bool:
        """True if the interval spans ``log10 LR = 0`` — the data direction
        (same vs different source) is not resolved at the ``1 - alpha`` level."""
        return self.lo_log10_lr < 0.0 < self.hi_log10_lr

    @property
    def point_lr(self) -> float:
        return float(10.0**self.point_log10_lr)

    @property
    def lo_lr(self) -> float:
        return float(10.0**self.lo_log10_lr)

    @property
    def hi_lr(self) -> float:
        return float(10.0**self.hi_log10_lr)


class BootstrapCalibration:
    """A reusable bootstrap ensemble of calibration models for one reference.

    Fitting the ensemble is the expensive step; once built, :meth:`interval`
    answers a credible interval for any query score cheaply. Build once per
    reference (see :func:`cached_bootstrap_calibration`) and reuse across queries.
    """

    def __init__(
        self,
        models: list[ScoreLRModel],
        *,
        method: str,
        resample: str,
        n_sources: int | None,
    ) -> None:
        if not models:
            raise ValueError("BootstrapCalibration needs at least one fitted replicate")
        self._models = models
        self.method = method
        self.resample = resample
        self.n_sources = n_sources

    @property
    def n_boot(self) -> int:
        return len(self._models)

    @classmethod
    def fit(
        cls,
        reference_scores: np.ndarray,
        reference_labels: np.ndarray,
        *,
        method: str = "logistic",
        lr_bound: str | float | None = "auto",
        n_boot: int = 1000,
        seed: int = 0,
        cluster_ids: np.ndarray | None = None,
    ) -> BootstrapCalibration:
        scores = np.asarray(reference_scores, dtype=np.float64)
        labels = np.asarray(reference_labels, dtype=np.float64)
        if scores.shape != labels.shape:
            raise ValueError("reference_scores and reference_labels must have the same shape")
        km = np.flatnonzero(labels == 1)
        knm = np.flatnonzero(labels == 0)
        if km.size == 0 or knm.size == 0:
            raise ValueError("reference must contain both KM (label 1) and KNM (label 0) rows")
        rng = np.random.default_rng(seed)
        models: list[ScoreLRModel] = []

        if cluster_ids is None:
            # Row-stratified: resample within each class so the class sizes — and
            # therefore the ELUB bound — are fixed across replicates.
            for _ in range(n_boot):
                idx = np.concatenate(
                    [
                        rng.choice(km, size=km.size, replace=True),
                        rng.choice(knm, size=knm.size, replace=True),
                    ]
                )
                models.append(
                    ScoreLRModel(method=method, lr_bound=lr_bound).fit(scores[idx], labels[idx])
                )
            return cls(models, method=method, resample="row-stratified", n_sources=None)

        # Clustered (block) bootstrap: resample whole sources/barrels.
        clusters = np.asarray(cluster_ids)
        if clusters.shape != labels.shape:
            raise ValueError("cluster_ids must have the same shape as the reference")
        uniq = np.unique(clusters)
        rows_by_cluster = {c: np.flatnonzero(clusters == c) for c in uniq}
        for _ in range(n_boot):
            sel = rng.choice(uniq, size=uniq.size, replace=True)
            idx = np.concatenate([rows_by_cluster[c] for c in sel])
            lab = labels[idx]
            if (lab == 1).sum() < 1 or (lab == 0).sum() < 1:
                continue  # a replicate that drew one class can't be calibrated; skip
            models.append(ScoreLRModel(method=method, lr_bound=lr_bound).fit(scores[idx], lab))
        if not models:
            raise ValueError(
                "no bootstrap replicate contained both classes; check cluster_ids / class balance"
            )
        return cls(models, method=method, resample="clustered", n_sources=int(uniq.size))

    def interval(
        self, query_score: float, *, point_log10_lr: float | None = None, alpha: float = 0.05
    ) -> LRInterval:
        """Percentile credible interval on ``log10 LR`` for one ``query_score``.

        ``point_log10_lr`` is the reported point estimate (the full-reference LR);
        if omitted the ensemble median is used as a fallback."""
        q = np.asarray([float(query_score)], dtype=np.float64)
        draws = np.array([float(np.log10(m.predict_lr(q)[0])) for m in self._models])
        lo = float(np.percentile(draws, 100.0 * alpha / 2.0))
        hi = float(np.percentile(draws, 100.0 * (1.0 - alpha / 2.0)))
        point = float(point_log10_lr) if point_log10_lr is not None else float(np.median(draws))
        return LRInterval(
            point_log10_lr=point,
            lo_log10_lr=lo,
            hi_log10_lr=hi,
            alpha=alpha,
            n_boot=len(self._models),
            method=self.method,
            resample=self.resample,
            n_sources=self.n_sources,
        )


_ENSEMBLE_CACHE: dict[str, BootstrapCalibration] = {}


def _ensemble_key(
    scores: np.ndarray,
    labels: np.ndarray,
    method: str,
    lr_bound: str | float | None,
    n_boot: int,
    seed: int,
    cluster_ids: np.ndarray | None,
) -> str:
    h = hashlib.sha1(usedforsecurity=False)  # content key for caching, not security
    h.update(np.ascontiguousarray(scores, dtype=np.float64).tobytes())
    h.update(np.ascontiguousarray(labels, dtype=np.float64).tobytes())
    if cluster_ids is not None:
        h.update(b"clusters")
        h.update(np.ascontiguousarray(cluster_ids).tobytes())
    h.update(repr((method, lr_bound, n_boot, seed)).encode())
    return h.hexdigest()


def cached_bootstrap_calibration(
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    *,
    method: str = "logistic",
    lr_bound: str | float | None = "auto",
    n_boot: int = 1000,
    seed: int = 0,
    cluster_ids: np.ndarray | None = None,
) -> BootstrapCalibration:
    """A :class:`BootstrapCalibration` for this reference + params, memoized by the
    reference's contents so a server fits each bundled reference's ensemble once."""
    scores = np.asarray(reference_scores, dtype=np.float64)
    labels = np.asarray(reference_labels, dtype=np.float64)
    key = _ensemble_key(scores, labels, method, lr_bound, n_boot, seed, cluster_ids)
    cal = _ENSEMBLE_CACHE.get(key)
    if cal is None:
        cal = BootstrapCalibration.fit(
            scores,
            labels,
            method=method,
            lr_bound=lr_bound,
            n_boot=n_boot,
            seed=seed,
            cluster_ids=cluster_ids,
        )
        _ENSEMBLE_CACHE[key] = cal
    return cal


def lr_credible_interval(
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    query_score: float,
    *,
    method: str = "logistic",
    lr_bound: str | float | None = "auto",
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
    cluster_ids: np.ndarray | None = None,
    point_log10_lr: float | None = None,
) -> LRInterval:
    """Credible interval on ``log10 LR`` for ``query_score`` calibrated against a
    reference population. Bootstraps the reference (row-stratified, or clustered if
    ``cluster_ids`` is given), refitting the bounded calibration each replicate.

    ``point_log10_lr`` is the reported point (the full-reference LR); when omitted
    it is computed with one extra full fit so the result is self-contained.
    """
    scores = np.asarray(reference_scores, dtype=np.float64)
    labels = np.asarray(reference_labels, dtype=np.float64)
    if point_log10_lr is None:
        model = ScoreLRModel(method=method, lr_bound=lr_bound).fit(scores, labels)
        lr = float(model.predict_lr(np.asarray([float(query_score)], dtype=np.float64))[0])
        point_log10_lr = float(np.log10(lr))
    cal = cached_bootstrap_calibration(
        scores,
        labels,
        method=method,
        lr_bound=lr_bound,
        n_boot=n_boot,
        seed=seed,
        cluster_ids=cluster_ids,
    )
    return cal.interval(query_score, point_log10_lr=point_log10_lr, alpha=alpha)
