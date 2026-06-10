"""Benchmark submission scoring — numpy-only, dependency-light by design.

This module re-implements the engine's metric semantics
(``verity.decision.metrics`` / ``verity.decision.lr``) without scikit-learn so
the catalog service (and the downloadable replication kit, which ships this
file verbatim) stays slim. Parity with the engine is pinned by test
(``tests/test_benchmark_scoring.py`` asserts engine-computed constants).

Semantics mirrored exactly:

* ``cllr``      — Brümmer & du Preez log-LR cost, prior 0.5.
* ``cllr_min``  — PAV (isotonic) calibration of the scores, posteriors clipped
  to ``[1e-4, 1 - 1e-4]``, posterior odds divided by the empirical prior odds,
  then ``cllr`` of those LRs (the discrimination floor).
* ``roc_auc``   — rank-based (Mann–Whitney) with average ranks for ties; equal
  to ``sklearn.metrics.roc_auc_score`` for binary labels.
* ``ece``       — expected calibration error of the LR-implied posteriors.

A *submission* is one likelihood ratio per frozen pair; scoring evaluates it
per frozen fold (test pairs only) and summarizes mean ± sd, exactly like the
engine's :func:`verity.benchmark.score_submission`.
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-4  # posterior clip — matches verity.decision.lr._EPS

PROTOCOL_VERSION = 1


def cllr(lr_km: np.ndarray, lr_knm: np.ndarray) -> float:
    """Log-likelihood-ratio cost (0 = perfect, 1 = uninformative)."""
    lr_km = np.asarray(lr_km, dtype=np.float64)
    lr_knm = np.asarray(lr_knm, dtype=np.float64)
    cost_km = np.mean(np.log2(1.0 + 1.0 / lr_km))
    cost_knm = np.mean(np.log2(1.0 + lr_knm))
    return float(0.5 * (cost_km + cost_knm))


def _pav_fit(scores: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Pool-adjacent-violators fit of ``labels`` on ``scores``: the
    least-squares non-decreasing posterior at each training score, ties in the
    score pooled first. Returns fitted values in the input order."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    order = np.argsort(scores, kind="mergesort")
    xs, ys = scores[order], labels[order]
    ux, inverse, counts = np.unique(xs, return_inverse=True, return_counts=True)
    means = np.bincount(inverse, weights=ys) / counts

    # Classic stack-based PAV over the tie-pooled blocks.
    vals: list[float] = []
    weights: list[float] = []
    sizes: list[int] = []  # how many unique-score blocks each pooled block spans
    for v, w in zip(means, counts.astype(np.float64), strict=True):
        vals.append(float(v))
        weights.append(float(w))
        sizes.append(1)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            w_new = weights[-2] + weights[-1]
            vals[-2] = (vals[-2] * weights[-2] + vals[-1] * weights[-1]) / w_new
            weights[-2] = w_new
            sizes[-2] += sizes[-1]
            vals.pop()
            weights.pop()
            sizes.pop()

    fitted_unique = np.repeat(np.asarray(vals), np.asarray(sizes))
    fitted_sorted = fitted_unique[inverse]
    out = np.empty_like(fitted_sorted)
    out[order] = fitted_sorted
    return out


def cllr_min(scores: np.ndarray, labels: np.ndarray) -> float:
    """``Cllr`` after PAV-optimal monotone calibration — the discrimination
    floor. Mirrors ``verity.decision.lr.cllr_min`` (posterior clip, empirical
    prior odds divided out)."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    prior = float(labels.mean())
    prior_odds = prior / (1.0 - prior) if 0.0 < prior < 1.0 else 1.0
    posterior = np.clip(_pav_fit(scores, labels), _EPS, 1.0 - _EPS)
    lr = (posterior / (1.0 - posterior)) / prior_odds
    return cllr(lr[labels == 1], lr[labels == 0])


def _average_ranks(x: np.ndarray) -> np.ndarray:
    """1-based ranks with ties given their average rank."""
    order = np.argsort(x, kind="mergesort")
    sx = x[order]
    ranks = np.empty(len(x), dtype=np.float64)
    i = 0
    n = len(x)
    while i < n:
        j = i
        while j + 1 < n and sx[j + 1] == sx[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def roc_auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Area under the ROC curve via the Mann–Whitney statistic (ties handled
    by average ranks) — identical to sklearn's ``roc_auc_score`` for binary
    labels."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    pos = labels == 1
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        raise ValueError("roc_auc needs both classes present")
    ranks = _average_ranks(scores)
    u = ranks[pos].sum() - n1 * (n1 + 1) / 2.0
    return float(u / (n1 * n0))


def ece(lr_km: np.ndarray, lr_knm: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error of the LRs' implied posteriors (prior 0.5)."""
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


def validate_lrs(lrs: np.ndarray) -> list[str]:
    """The junk-LR guard: every value must be a finite, strictly positive
    likelihood ratio. Returns human-readable problems (empty = valid)."""
    lrs = np.asarray(lrs, dtype=np.float64)
    problems = []
    n_bad = int((~np.isfinite(lrs)).sum())
    if n_bad:
        problems.append(f"{n_bad} non-finite LR(s) — every pair needs a finite LR")
    n_neg = int((np.isfinite(lrs) & (lrs <= 0.0)).sum())
    if n_neg:
        problems.append(f"{n_neg} LR(s) <= 0 — a likelihood ratio is strictly positive")
    return problems


def score_submission(
    lrs: np.ndarray,
    labels: np.ndarray,
    folds: list[tuple[int, np.ndarray]],
) -> dict:
    """Score one-LR-per-pair against frozen folds (``(fold_index, pair_indices)``
    tuples). Output shape mirrors ``verity.benchmark.score_submission``: per-fold
    Cllr / Cllr_min / AUC, mean ± sd, pooled metrics, and the headline
    ``calibration_loss``."""
    lrs = np.asarray(lrs, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    if len(lrs) != len(labels):
        raise ValueError(f"{len(lrs)} LRs for {len(labels)} pairs")
    problems = validate_lrs(lrs)
    if problems:
        raise ValueError("; ".join(problems))
    log_lr = np.log10(lrs)

    rows = []
    for fold_index, idx in folds:
        idx = np.asarray(idx, dtype=int)
        lf, yf = lrs[idx], labels[idx]
        if yf.sum() < 1 or (yf == 0).sum() < 1:
            continue
        rows.append(
            {
                "fold": int(fold_index),
                "n_pairs": int(len(idx)),
                "cllr": cllr(lf[yf == 1], lf[yf == 0]),
                "cllr_min": cllr_min(log_lr[idx], yf),
                "auc": roc_auc(log_lr[idx], yf),
            }
        )
    if not rows:
        raise ValueError("no scorable folds (every fold lacked a KM or KNM test pair)")

    c = np.array([r["cllr"] for r in rows])
    cm = np.array([r["cllr_min"] for r in rows])
    au = np.array([r["auc"] for r in rows])
    return {
        "protocol_version": PROTOCOL_VERSION,
        "n_folds": len(rows),
        "cllr": float(c.mean()),
        "cllr_std": float(c.std()),
        "cllr_min": float(cm.mean()),
        "cllr_min_std": float(cm.std()),
        "auc": float(au.mean()),
        "auc_std": float(au.std()),
        "calibration_loss": float(c.mean() - cm.mean()),
        "pooled": {
            "n_pairs": int(len(labels)),
            "n_km": int(labels.sum()),
            "n_knm": int((labels == 0).sum()),
            "cllr": cllr(lrs[labels == 1], lrs[labels == 0]),
            "cllr_min": cllr_min(log_lr, labels),
            "auc": roc_auc(log_lr, labels),
            "ece": ece(lrs[labels == 1], lrs[labels == 0]),
        },
        "folds": rows,
    }
