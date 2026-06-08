"""Source-disjoint validation of the calibrated LR — the honest generalization
claim.

A likelihood-ratio system must be characterized on data it was *not* calibrated
on, with no source (barrel) spanning both the train and test sides. This is the
discipline whose absence the Cuellar et al. (2024) critique flags. The result is a
weight of evidence with a characterized cost (``Cllr``) on a named dataset — not a
field-wide error-rate claim.

This module is the single home for that protocol so the validation report
(:mod:`verity.report_validation`), the fusion ablation, and offline scripts all
report the *same* numbers.
"""

from __future__ import annotations

import numpy as np

from .lr import ScoreLRModel, cllr_min
from .metrics import cllr, roc_auc


def barrel_disjoint_folds(
    scores: np.ndarray,
    labels: np.ndarray,
    barrels_a: np.ndarray,
    barrels_b: np.ndarray,
    *,
    n_splits: int = 10,
    test_frac: float = 0.4,
    seed: int = 0,
) -> list[dict]:
    """Calibrate on train barrels, score held-out test barrels; no barrel spans
    both. Pairs straddling the split are dropped. Each fold reports test
    ``cllr`` (the deployed bounded calibration), ``cllr_min`` (PAV floor) and
    ``auc``."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    barrels = sorted(set(barrels_a.tolist()) | set(barrels_b.tolist()))
    rng = np.random.default_rng(seed)
    n_test = max(2, round(len(barrels) * test_frac))
    rows: list[dict] = []
    for _ in range(n_splits):
        test_b = set(rng.permutation(barrels)[:n_test].tolist())
        in_test = np.array(
            [x in test_b and y in test_b for x, y in zip(barrels_a, barrels_b, strict=True)]
        )
        in_train = np.array(
            [x not in test_b and y not in test_b for x, y in zip(barrels_a, barrels_b, strict=True)]
        )
        if labels[in_train].sum() < 3 or labels[in_test].sum() < 1:
            continue
        model = ScoreLRModel().fit(scores[in_train], labels[in_train])
        lr = model.predict_lr(scores[in_test])
        rows.append(
            {
                "cllr": cllr(lr[labels[in_test] == 1], lr[labels[in_test] == 0]),
                "cllr_min": cllr_min(scores[in_test], labels[in_test]),
                "auc": roc_auc(scores[in_test], labels[in_test]),
            }
        )
    return rows


def summarize_folds(folds: list[dict]) -> dict | None:
    """Mean ± sd of the per-fold metrics, plus the mean calibration loss. None if
    there were too few barrels for a disjoint split."""
    if not folds:
        return None
    cllr_arr = np.array([f["cllr"] for f in folds])
    cllr_min_arr = np.array([f["cllr_min"] for f in folds])
    auc_arr = np.array([f["auc"] for f in folds])
    return {
        "n_folds": len(folds),
        "cllr_mean": float(cllr_arr.mean()),
        "cllr_std": float(cllr_arr.std()),
        "cllr_min_mean": float(cllr_min_arr.mean()),
        "cllr_min_std": float(cllr_min_arr.std()),
        "auc_mean": float(auc_arr.mean()),
        "auc_std": float(auc_arr.std()),
        "calibration_loss": float(cllr_arr.mean() - cllr_min_arr.mean()),
    }
