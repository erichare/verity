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
