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


def margin(scores: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    """How *distinctly different* the same-source and different-source score
    distributions are — separation, not mere rank-separability.

    ``AUC`` can be 1.0 while the two distributions sit almost on top of each
    other (perfectly ordered but barely apart); that narrow margin calibrates
    poorly and does not generalize. These measures quantify the gap the system is
    trying to widen:

    * ``cohens_d`` — standardized mean difference
      ``(mean_KM - mean_KNM) / pooled_sd``. Scale-free; bigger is wider.
    * ``pct_gap`` — robust separation ``percentile(KM, 5) - percentile(KNM, 95)``.
      Positive ⇒ a near-non-overlapping margin between the bulk of each class;
      negative ⇒ the tails still interleave.
    """
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    km = scores[labels == 1]
    knm = scores[labels == 0]
    if km.size == 0 or knm.size == 0:
        return {"cohens_d": float("nan"), "pct_gap": float("nan")}
    n1, n0 = km.size, knm.size
    pooled_var = ((n1 - 1) * km.var(ddof=1) + (n0 - 1) * knm.var(ddof=1)) / max(n1 + n0 - 2, 1)
    pooled_sd = float(np.sqrt(pooled_var))
    cohens_d = (km.mean() - knm.mean()) / pooled_sd if pooled_sd > 0 else 0.0
    pct_gap = float(np.percentile(km, 5) - np.percentile(knm, 95))
    return {"cohens_d": float(cohens_d), "pct_gap": pct_gap}


def lr_separation(lr_km: np.ndarray, lr_knm: np.ndarray) -> float:
    """Mean ``log10 LR`` of same-source comparisons minus that of different-source
    ones — the margin in evidence space. Larger ⇒ the system reports decisively
    different weights of evidence for matches vs non-matches."""
    lr_km = np.asarray(lr_km, dtype=np.float64)
    lr_knm = np.asarray(lr_knm, dtype=np.float64)
    return float(np.mean(np.log10(lr_km)) - np.mean(np.log10(lr_knm)))
