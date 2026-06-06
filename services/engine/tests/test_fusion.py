"""Tests for land-level LR fusion (the margin-widening combination)."""

import numpy as np

from verity import roc_auc
from verity.decision.fusion import LandFusionModel


def _diag_pairs(rng, n, mu, n_lands=6):
    """``n`` bullet pairs, each ``n_lands`` diagonal land CCFs ~ N(mu, 0.2)."""
    return [np.clip(rng.normal(mu, 0.2, n_lands), -1.0, 1.0) for _ in range(n)]


def test_fusion_separates_out_of_sample():
    rng = np.random.default_rng(0)
    km = _diag_pairs(rng, 60, 0.55)
    knm = _diag_pairs(rng, 300, 0.2)
    diag = km + knm
    labels = np.array([1] * len(km) + [0] * len(knm))

    order = rng.permutation(len(diag))
    train, test = order[: len(order) // 2], order[len(order) // 2 :]
    model = LandFusionModel.fit([diag[i] for i in train], labels[train])

    fused_test = model.fused_scores([diag[i] for i in test])
    assert roc_auc(fused_test, labels[test]) > 0.9


def test_fused_score_increases_with_concordance():
    rng = np.random.default_rng(1)
    model = LandFusionModel.fit(
        _diag_pairs(rng, 40, 0.6) + _diag_pairs(rng, 200, 0.15),
        np.array([1] * 40 + [0] * 200),
    )
    assert model.fused_score(np.full(6, 0.7)) > model.fused_score(np.full(6, 0.1))


def test_fused_lr_accumulates_beyond_a_single_land():
    # Six concordant lands assert more evidence than any single land can — the
    # accumulation that widens the KM margin past the per-comparison LR bound.
    rng = np.random.default_rng(2)
    model = LandFusionModel.fit(
        _diag_pairs(rng, 40, 0.6) + _diag_pairs(rng, 200, 0.15),
        np.array([1] * 40 + [0] * 200),
    )
    single_lr = float(model.calibrator.predict_lr(np.array([0.7]))[0])
    fused_lr = 10.0 ** model.fused_score(np.full(6, 0.7))
    assert fused_lr > single_lr
