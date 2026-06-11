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

Two environment knobs tune that cost without touching the audit properties:

* ``VERITY_LR_BOOTSTRAP_N`` — the replicate count used wherever ``n_boot`` is not
  passed explicitly (default 1000; see :func:`default_n_boot`). CI and small
  machines can lower it. ``n_boot`` is recorded in the comparison recipe's
  content-addressed params, so a changed count (correctly) yields different
  recipe handles.
* ``VERITY_ENSEMBLE_CACHE_DIR`` — when set, fitted *logistic* ensembles persist to
  a content-keyed ``.npz`` under that directory, so a fresh process (deploy, CI
  run, local pytest) skips the rebuild. The key covers the reference contents and
  every fit parameter (method, bound, n_boot, seed, clusters), and an entry stores
  each replicate's exact fitted parameters — a cache hit reproduces the same
  intervals as a cold fit, replicate for replicate.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .lr import ScoreLRModel

__all__ = [
    "LRInterval",
    "BootstrapCalibration",
    "cached_bootstrap_calibration",
    "default_n_boot",
    "lr_credible_interval",
]

logger = logging.getLogger(__name__)

_DEFAULT_N_BOOT = 1000


def default_n_boot() -> int:
    """The bootstrap replicate count used when ``n_boot`` is not given explicitly:
    ``VERITY_LR_BOOTSTRAP_N`` when set, else 1000. Read at call time so a process
    honours the environment it actually runs under (and tests can monkeypatch it).
    A malformed value raises rather than silently changing the statistics."""
    raw = os.environ.get("VERITY_LR_BOOTSTRAP_N")
    if raw is None or not raw.strip():
        return _DEFAULT_N_BOOT
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"VERITY_LR_BOOTSTRAP_N must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"VERITY_LR_BOOTSTRAP_N must be positive, got {value}")
    return value


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
        n_boot: int | None = None,
        seed: int = 0,
        cluster_ids: np.ndarray | None = None,
    ) -> BootstrapCalibration:
        n_boot = default_n_boot() if n_boot is None else int(n_boot)
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

# Bump when the on-disk ensemble layout changes; mismatched entries are refit.
# Entries store *fit output* (each replicate's parameters), so they survive sklearn
# upgrades that only change fitting internals — but then a hit reproduces the fit
# the entry was built under, not what a refit would now produce. Clear the cache
# dir on upgrades where that distinction matters.
_CACHE_FORMAT_VERSION = 1


class _FrozenLogistic:
    """A rehydrated 1-D Platt fit — a ``predict_proba``-compatible stand-in for the
    fitted sklearn ``LogisticRegression``. Computes ``expit(coef·s + intercept)``
    with the same elementary float ops as sklearn's binary ``predict_proba``, so a
    reloaded replicate reproduces the original's LRs bit for bit. (That claim is
    exact for the single-score queries :meth:`BootstrapCalibration.interval`
    issues; batched queries would put it at the mercy of BLAS rounding.)"""

    def __init__(self, coef: float, intercept: float) -> None:
        self.coef_ = np.array([[float(coef)]])
        self.intercept_ = np.array([float(intercept)])

    def predict_proba(self, scores: np.ndarray) -> np.ndarray:
        from scipy.special import expit  # sklearn's own sigmoid — identical rounding

        z = np.asarray(scores, dtype=np.float64).ravel() * self.coef_[0, 0] + self.intercept_[0]
        p_same = expit(z)
        return np.column_stack([1.0 - p_same, p_same])


def _disk_cache_path(key: str) -> Path | None:
    """Where the ensemble for ``key`` persists, or None when the disk cache is off
    (``VERITY_ENSEMBLE_CACHE_DIR`` unset) or unusable. The cache is an optional
    optimization, so an unusable directory degrades to refitting, loudly."""
    raw = os.environ.get("VERITY_ENSEMBLE_CACHE_DIR")
    if raw is None or not raw.strip():
        return None
    root = Path(raw)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("VERITY_ENSEMBLE_CACHE_DIR %r is unusable (%s); refitting", raw, exc)
        return None
    return root / f"{key}.npz"  # key is a hex digest — no path traversal possible


def _save_ensemble(path: Path, cal: BootstrapCalibration) -> None:
    """Persist a fitted logistic ensemble: each replicate's exact fitted parameters
    (slope, intercept, resolved LR bound). Written atomically (temp file + rename)
    so concurrent workers and killed processes never leave a torn entry."""
    coef = np.array([float(m._model.coef_[0, 0]) for m in cal._models])
    intercept = np.array([float(m._model.intercept_[0]) for m in cal._models])
    log_bound = np.array(
        [np.nan if m._log_bound is None else float(m._log_bound) for m in cal._models]
    )
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".npz.tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            np.savez(
                fh,
                format_version=np.array(_CACHE_FORMAT_VERSION),
                resample=np.array(cal.resample),
                n_sources=np.array(-1 if cal.n_sources is None else int(cal.n_sources)),
                coef=coef,
                intercept=intercept,
                log_bound=log_bound,
            )
        os.replace(tmp, path)
    except Exception as exc:  # noqa: BLE001 — persisting is best-effort; never break compare
        logger.warning("could not persist bootstrap ensemble to %s: %s", path, exc)
        with contextlib.suppress(OSError):
            os.unlink(tmp)


def _load_ensemble(
    path: Path, *, method: str, lr_bound: str | float | None
) -> BootstrapCalibration | None:
    """Rehydrate a persisted ensemble, or None when the entry is missing, malformed,
    or from another format version — the caller then refits (and overwrites it)."""
    try:
        with np.load(path) as data:  # allow_pickle stays False: parameters only
            if int(data["format_version"]) != _CACHE_FORMAT_VERSION:
                return None
            coef = np.asarray(data["coef"], dtype=np.float64)
            intercept = np.asarray(data["intercept"], dtype=np.float64)
            log_bound = np.asarray(data["log_bound"], dtype=np.float64)
            resample = str(data["resample"].item())
            n_sources = int(data["n_sources"])
        if not (coef.shape == intercept.shape == log_bound.shape) or coef.ndim != 1:
            raise ValueError("replicate arrays disagree in shape")
        if coef.size == 0:
            raise ValueError("entry holds no replicates")
    except Exception as exc:  # noqa: BLE001 — a bad cache entry must never break compare
        logger.warning("ignoring unreadable bootstrap-ensemble cache %s: %s", path, exc)
        return None
    models: list[ScoreLRModel] = []
    for c, b, lb in zip(coef, intercept, log_bound, strict=True):
        m = ScoreLRModel(method=method, lr_bound=lr_bound)
        m._model = _FrozenLogistic(c, b)
        m._prior_odds = 1.0  # the logistic fit is balanced; see ScoreLRModel.fit
        m._log_bound = None if np.isnan(lb) else float(lb)
        models.append(m)
    return BootstrapCalibration(
        models, method=method, resample=resample, n_sources=None if n_sources < 0 else n_sources
    )


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
        # The fit uses cluster identity plus the sorted-unique order (the RNG draws
        # whole clusters from np.unique(clusters)), so hash the canonical int64
        # inverse codes: labellings the fit cannot tell apart (int32 vs int64, any
        # relabelling that preserves the sort order) key identically, while one the
        # resampler would draw differently keys differently.
        codes = np.unique(np.asarray(cluster_ids), return_inverse=True)[1]
        h.update(np.ascontiguousarray(codes, dtype=np.int64).tobytes())
    h.update(repr((method, lr_bound, n_boot, seed)).encode())
    return h.hexdigest()


def cached_bootstrap_calibration(
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    *,
    method: str = "logistic",
    lr_bound: str | float | None = "auto",
    n_boot: int | None = None,
    seed: int = 0,
    cluster_ids: np.ndarray | None = None,
) -> BootstrapCalibration:
    """A :class:`BootstrapCalibration` for this reference + params, memoized by the
    reference's contents so a server fits each bundled reference's ensemble once.
    ``n_boot=None`` resolves :func:`default_n_boot` (``VERITY_LR_BOOTSTRAP_N``).

    When ``VERITY_ENSEMBLE_CACHE_DIR`` is set, logistic ensembles also persist to a
    content-keyed file there, so a *fresh process* (deploy, CI run) skips the
    rebuild. The key covers the reference arrays and every fit parameter, and a hit
    rehydrates the exact fitted replicates — same seed, method, and per-replicate
    bound as a cold fit. Isotonic ensembles stay in-memory only (their fitted state
    is variable-length; the deployed path is logistic)."""
    scores = np.asarray(reference_scores, dtype=np.float64)
    labels = np.asarray(reference_labels, dtype=np.float64)
    n_boot = default_n_boot() if n_boot is None else int(n_boot)
    key = _ensemble_key(scores, labels, method, lr_bound, n_boot, seed, cluster_ids)
    cal = _ENSEMBLE_CACHE.get(key)
    if cal is not None:
        return cal
    disk = _disk_cache_path(key) if method == "logistic" else None
    if disk is not None and disk.exists():
        cal = _load_ensemble(disk, method=method, lr_bound=lr_bound)
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
        if disk is not None:
            _save_ensemble(disk, cal)
    _ENSEMBLE_CACHE[key] = cal
    return cal


def lr_credible_interval(
    reference_scores: np.ndarray,
    reference_labels: np.ndarray,
    query_score: float,
    *,
    method: str = "logistic",
    lr_bound: str | float | None = "auto",
    n_boot: int | None = None,
    alpha: float = 0.05,
    seed: int = 0,
    cluster_ids: np.ndarray | None = None,
    point_log10_lr: float | None = None,
) -> LRInterval:
    """Credible interval on ``log10 LR`` for ``query_score`` calibrated against a
    reference population. Bootstraps the reference (row-stratified, or clustered if
    ``cluster_ids`` is given), refitting the bounded calibration each replicate.
    ``n_boot=None`` resolves :func:`default_n_boot` (``VERITY_LR_BOOTSTRAP_N``).

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
