"""Synthetic tests for the areal (impressed-mark) comparison path."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter, rotate

from verity.areal import areal_score, areal_signature
from verity.surface import Surface


def _unit(z: np.ndarray) -> np.ndarray:
    z = z - z.mean()
    return z / (np.linalg.norm(z) + 1e-12)


def test_areal_score_high_for_rotated_same_source():
    rng = np.random.default_rng(0)
    base = gaussian_filter(rng.normal(size=(128, 128)), 3)  # smooth areal structure
    a = _unit(base)
    b = _unit(rotate(base, 30.0, reshape=False, order=1))  # same source, rotated 30deg
    # the rotation search (incl. 330deg) should recover the match
    assert areal_score(a, b, angles=range(0, 360, 10)) > 0.5


def test_areal_score_low_for_different_source():
    rng = np.random.default_rng(1)
    a = _unit(gaussian_filter(rng.normal(size=(128, 128)), 3))
    b = _unit(gaussian_filter(rng.normal(size=(128, 128)), 3))
    assert areal_score(a, b, angles=range(0, 360, 30)) < 0.3


def test_areal_signature_shape_norm_and_mask():
    rng = np.random.default_rng(2)
    z = rng.normal(size=(300, 300))
    z[:60, :] = np.nan  # a masked band (like the firing-pin hole / off-primer)
    sig = areal_signature(Surface(heights=z, dx=3e-6, dy=3e-6), size=128, decimate=2)
    assert sig.shape == (128, 128)
    assert abs(np.linalg.norm(sig) - 1.0) < 1e-6  # unit norm
