"""Forensic evaluation metrics for a likelihood-ratio system.

``Cllr`` (the log-likelihood-ratio cost, Brümmer & du Preez 2006) is the field's
gold-standard summary: ``0`` is perfect, ``1`` is an uninformative system that
always reports ``LR = 1``. ``Cllr`` decomposes into discrimination and
calibration; the gap ``Cllr - Cllr_min`` is the calibration loss.
"""

from __future__ import annotations

import numpy as np


def cllr(lr_km: np.ndarray, lr_knm: np.ndarray) -> float:
    """Log-likelihood-ratio cost from the LRs of true same-source (``lr_km``) and
    true different-source (``lr_knm``) comparisons. Implied prior 0.5."""
    lr_km = np.asarray(lr_km, dtype=np.float64)
    lr_knm = np.asarray(lr_knm, dtype=np.float64)
    cost_km = np.mean(np.log2(1.0 + 1.0 / lr_km))
    cost_knm = np.mean(np.log2(1.0 + lr_knm))
    return float(0.5 * (cost_km + cost_knm))


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Area under the ROC curve (``labels``: 1 = same-source, 0 = different)."""
    from sklearn.metrics import roc_auc_score

    return float(roc_auc_score(labels, scores))


def eer(scores: np.ndarray, labels: np.ndarray) -> float:
    """Equal error rate."""
    from sklearn.metrics import roc_curve

    fpr, tpr, _ = roc_curve(labels, scores)
    fnr = 1.0 - tpr
    idx = int(np.nanargmin(np.abs(fnr - fpr)))
    return float((fpr[idx] + fnr[idx]) / 2.0)


def ece(lr_km: np.ndarray, lr_knm: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error of the LRs' implied posteriors (prior 0.5).

    Each LR maps to a same-source posterior ``p = LR / (1 + LR)``; comparisons are
    binned by ``p`` and a bin's mean posterior is compared to its empirical
    same-source fraction. ``0`` is perfectly reliable."""
    lr_km = np.asarray(lr_km, dtype=np.float64)
    lr_knm = np.asarray(lr_knm, dtype=np.float64)
    lr = np.concatenate([lr_km, lr_knm])
    y = np.concatenate([np.ones_like(lr_km), np.zeros_like(lr_knm)])
    p = lr / (1.0 + lr)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        in_bin = (p >= lo) & (p <= hi) if hi == 1.0 else (p >= lo) & (p < hi)
        if in_bin.any():
            total += abs(p[in_bin].mean() - y[in_bin].mean()) * in_bin.mean()
    return float(total)


def tippett(lr_km: np.ndarray, lr_knm: np.ndarray, n: int = 100):
    """Tippett-plot data: over a grid of LR thresholds, the proportion of
    same-source and different-source comparisons with ``LR >= threshold``.
    Returns ``(thresholds, km_proportion, knm_proportion)``."""
    lr_km = np.asarray(lr_km, dtype=np.float64)
    lr_knm = np.asarray(lr_knm, dtype=np.float64)
    both = np.concatenate([lr_km, lr_knm])
    lo, hi = np.log10(both.min() + 1e-12), np.log10(both.max() + 1e-12)
    thresholds = np.logspace(lo, hi, n)
    km_prop = np.array([np.mean(lr_km >= t) for t in thresholds])
    knm_prop = np.array([np.mean(lr_knm >= t) for t in thresholds])
    return thresholds, km_prop, knm_prop
