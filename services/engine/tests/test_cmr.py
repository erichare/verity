"""Tests for Congruent Matching Regions — the generic core and both instantiations."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, rotate

from verity.cmr import cmr_count, cmr_score_1d, cmr_score_2d


def test_cmr_count_is_largest_congruent_cluster():
    votes = [((3.0,), 0.9), ((3.4,), 0.8), ((2.7,), 0.85), ((3.1,), 0.7),  # cluster ~3
             ((30.0,), 0.9), ((55.0,), 0.9)]  # two scattered
    assert cmr_count(votes, corr_thresh=0.5, transform_tol=(2.0,)) == 4
    # weak registrations don't vote
    assert cmr_count([((3.0,), 0.1), ((3.0,), 0.2)], corr_thresh=0.5, transform_tol=(2.0,)) == 0


def test_cmr_1d_same_source_more_congruent_than_different():
    rng = np.random.default_rng(0)
    base = gaussian_filter(rng.normal(size=900), 2)
    same = np.roll(base, 40) + rng.normal(0, 0.05, 900)  # same source, global shift
    diff = gaussian_filter(rng.normal(size=900), 2)
    assert cmr_score_1d(base, same) > cmr_score_1d(base, diff)
    assert cmr_score_1d(base, same) >= 4  # most windows agree on the common lag


def test_cmr_2d_same_source_more_congruent_than_different():
    rng = np.random.default_rng(1)

    def unit(z):
        z = z - z.mean()
        return z / (np.linalg.norm(z) + 1e-12)

    base = gaussian_filter(rng.normal(size=(140, 140)), 3)
    same = unit(rotate(base, 10.0, reshape=False, order=1))  # same source, rotated
    diff = unit(gaussian_filter(rng.normal(size=(140, 140)), 3))
    a = unit(base)
    sb = cmr_score_2d(a, same, grid=5, angles=range(-15, 16, 5))
    sc = cmr_score_2d(a, diff, grid=5, angles=range(-15, 16, 5))
    assert sb > sc
