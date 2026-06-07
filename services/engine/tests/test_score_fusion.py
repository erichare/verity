"""Tests for best-of-both score fusion."""

from __future__ import annotations

import numpy as np

from verity.decision.score_fusion import FusionLRModel, fused_cllr


def test_fusion_is_no_worse_than_the_better_feature():
    """Two scores: feature 0 is informative, feature 1 is pure noise. Fusion must
    track the informative one (Cllr well below the uninformative 1.0)."""
    rng = np.random.default_rng(0)
    n = 400
    y = np.r_[np.ones(n // 2), np.zeros(n // 2)]
    good = np.r_[rng.normal(2, 1, n // 2), rng.normal(-2, 1, n // 2)]  # separates
    noise = rng.normal(0, 1, n)  # carries nothing
    feats = np.column_stack([good, noise])
    # train/test split
    idx = rng.permutation(n)
    tr, te = idx[: n // 2], idx[n // 2 :]
    c = fused_cllr(feats[tr], y[tr], feats[te], y[te])
    assert c < 0.6  # learned to use the good feature, ignore the noise


def test_fusion_lr_bound_caps_evidence():
    rng = np.random.default_rng(1)
    y = np.r_[np.ones(30), np.zeros(30)]  # n_minority = 30 -> cap ~10^1.48
    x = np.r_[rng.normal(8, 1, 30), rng.normal(-8, 1, 30)].reshape(-1, 1)
    lr = FusionLRModel(lr_bound="auto").fit(x, y).predict_lr(x)
    assert lr.max() <= 10.0 ** np.log10(30) + 1e-6
    unbounded = FusionLRModel(lr_bound=None).fit(x, y).predict_lr(x)
    assert unbounded.max() > lr.max()
