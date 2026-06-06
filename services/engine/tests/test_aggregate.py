"""Tests for bullet-to-bullet aggregation and the CCF-matrix structure features."""

import numpy as np

from verity.aggregate import (
    BulletComparison,
    best_diagonal,
    bullet_comparison,
    bullet_score,
    diagonal_means,
    land_ccf_matrix,
)
from verity.registration import align_1d


def _ref_bullet_score(sigs_a, sigs_b):
    """The original inline implementation from hamby_km_knm, kept as an oracle."""
    n, mm = len(sigs_a), len(sigs_b)
    ccf = np.array([[align_1d(a, b)[1] for b in sigs_b] for a in sigs_a])
    return float(max(np.mean([ccf[i, (i + k) % mm] for i in range(n)]) for k in range(mm)))


def _cmp_from_ccf(ccf, lags=None):
    """Build a BulletComparison straight from a CCF matrix (mirrors the matrix->
    object step in bullet_comparison) so feature tests can plant structure."""
    offset, diag = best_diagonal(ccf)
    mm = ccf.shape[1]
    lags = np.zeros_like(ccf) if lags is None else lags
    diag_lags = np.array([lags[i, (i + offset) % mm] for i in range(ccf.shape[0])])
    return BulletComparison(ccf=ccf, lags=lags, offset=offset, diag_ccf=diag, diag_lags=diag_lags)


def test_bullet_score_matches_reference():
    rng = np.random.default_rng(0)
    sigs_a = [rng.standard_normal(120) for _ in range(6)]
    sigs_b = [s + 0.1 * rng.standard_normal(120) for s in sigs_a]
    assert bullet_score(sigs_a, sigs_b) == _ref_bullet_score(sigs_a, sigs_b)


def test_bullet_score_empty_is_nan():
    assert np.isnan(bullet_score([], [np.ones(10)]))
    assert bullet_comparison([], []) is None


def test_land_ccf_matrix_shape():
    a = [np.ones(10), np.arange(10.0)]
    b = [np.ones(10), np.arange(10.0), np.zeros(10)]
    ccf, lags = land_ccf_matrix(a, b)
    assert ccf.shape == (2, 3)
    assert lags.shape == (2, 3)


def test_best_diagonal_finds_planted_offset():
    rng = np.random.default_rng(1)
    ccf = 0.1 * rng.standard_normal((6, 6))
    for i in range(6):
        ccf[i, (i + 2) % 6] = 0.9
    offset, diag = best_diagonal(ccf)
    assert offset == 2
    assert np.allclose(diag, 0.9)


def test_diagonal_means_length():
    ccf = np.ones((6, 6))
    assert diagonal_means(ccf).shape == (6,)


def test_km_like_matrix_beats_knm_on_structure_features():
    n = 6
    km = np.full((n, n), 0.1)
    for i in range(n):
        km[i, i] = 0.85  # one clean diagonal
    knm = np.full((n, n), 0.3)  # flat: no special diagonal
    kc, nc = _cmp_from_ccf(km), _cmp_from_ccf(knm)
    assert kc.diag_contrast > nc.diag_contrast
    assert kc.offset_margin > nc.offset_margin
    assert kc.diag_min > nc.diag_min
    # all features are oriented higher = more KM-like
    assert set(kc.features()) == {
        "diag_mean",
        "diag_min",
        "diag_contrast",
        "offset_margin",
        "lag_coherence",
    }


def test_lag_coherence_higher_for_consistent_lags():
    n = 6
    ccf = np.eye(n) * 0.8 + 0.1
    coherent = _cmp_from_ccf(ccf, lags=np.zeros((n, n)))
    scatter = np.zeros((n, n))
    for i in range(n):
        scatter[i, i] = i * 5
    scattered = _cmp_from_ccf(ccf, lags=scatter)
    assert coherent.lag_coherence == 1.0  # zero lag spread
    assert coherent.lag_coherence > scattered.lag_coherence
