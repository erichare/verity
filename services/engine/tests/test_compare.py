"""Tests for end-to-end surface comparison (compare_surfaces)."""

from __future__ import annotations

import numpy as np
import pytest

from verity.compare import comparison_score, compare_surfaces
from verity.surface import Surface


def _striated(shift: int = 0) -> Surface:
    x = np.arange(400)
    prof = np.sin(2 * np.pi * x / 12.0) + 0.3 * np.sin(2 * np.pi * x / 5.0)
    return Surface(heights=np.tile(np.roll(prof, shift), (60, 1)), dx=1e-6, dy=1e-6)


def _areal(seed: int) -> Surface:
    from scipy.ndimage import gaussian_filter

    rng = np.random.default_rng(seed)
    z = gaussian_filter(rng.normal(size=(200, 200)), 3)
    return Surface(heights=z, dx=3e-6, dy=3e-6)


def _ref():
    return np.r_[np.full(20, 0.9), np.full(60, 0.1)], np.r_[np.ones(20), np.zeros(60)]


def test_compare_striated_returns_valid_report():
    scores, labels = _ref()
    rep = compare_surfaces(
        _striated(0), _striated(7), domain="striated",
        reference_scores=scores, reference_labels=labels, reference_name="synthetic",
    )
    assert rep.domain == "striated" and rep.score_kind == "ccf"
    assert np.isfinite(rep.likelihood_ratio) and rep.reference["name"] == "synthetic"
    assert rep.provenance["scorer"] == "ccf"


def test_compare_impressed_returns_valid_report():
    scores, labels = _ref()
    rep = compare_surfaces(
        _areal(0), _areal(1), domain="impressed",
        reference_scores=scores, reference_labels=labels, reference_name="synthetic",
    )
    assert rep.domain == "impressed" and rep.score_kind == "areal-ccf"
    assert np.isfinite(rep.likelihood_ratio)


def test_unknown_domain_raises():
    with pytest.raises(ValueError, match="domain"):
        comparison_score(_striated(), _striated(), domain="footwear")
