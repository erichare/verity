"""Tests for the pluggable bullet scorers."""

from __future__ import annotations

import numpy as np

from verity.aggregate import bullet_comparison
from verity.decision.scorer import ContrastScorer, FusionScorer


def _km_comparison(seed: int):
    """A same-source-like bullet pair: B's lands are A's lands + small noise."""
    rng = np.random.default_rng(seed)
    a = [rng.normal(size=200) for _ in range(6)]
    b = [x + rng.normal(scale=0.05, size=200) for x in a]
    return bullet_comparison(a, b)


def _knm_comparison(seed: int):
    """A different-source-like pair: independent lands."""
    rng = np.random.default_rng(seed)
    a = [rng.normal(size=200) for _ in range(6)]
    b = [rng.normal(size=200) for _ in range(6)]
    return bullet_comparison(a, b)


def test_contrast_scorer_returns_diag_contrast():
    cmp = _km_comparison(0)
    assert ContrastScorer().score(cmp) == cmp.diag_contrast
    assert ContrastScorer().name == "bullet-contrast"


def test_fusion_scorer_fits_and_scores():
    comps = [_km_comparison(i) for i in range(6)] + [_knm_comparison(100 + i) for i in range(6)]
    labels = np.array([1] * 6 + [0] * 6, dtype=float)
    scorer = FusionScorer.fit(comps, labels)
    # KM-like pairs should score above KNM-like pairs on average
    km_mean = np.mean([scorer.score(c) for c in comps[:6]])
    knm_mean = np.mean([scorer.score(c) for c in comps[6:]])
    assert km_mean > knm_mean
    # the fusion is glass-box: one coefficient per named feature
    coefs = scorer.coefficients
    assert set(coefs) == {"diag_mean", "diag_contrast", "lag_coherence"}
    assert all(np.isfinite(v) for v in coefs.values())
