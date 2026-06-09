"""Tests for end-to-end surface comparison (compare_surfaces)."""

from __future__ import annotations

import numpy as np
import pytest

from verity.compare import compare_surfaces, comparison_score
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


def test_compare_with_previews_striated_has_previews_and_attribution():
    """A single-land striated comparison renders both surfaces + matched-striae bands."""
    from verity.compare import compare_with_previews

    scores, labels = _ref()
    report, previews = compare_with_previews(
        _striated(0), _striated(0), domain="striated",  # identical -> congruent striae
        reference_scores=scores, reference_labels=labels, reference_name="synthetic",
    )
    assert report.score_kind == "ccf"
    assert set(previews) == {"a", "b"} and len(previews["a"]) > 0
    assert len(report.attribution) > 0


def test_compare_impressed_returns_valid_report():
    scores, labels = _ref()
    rep = compare_surfaces(
        _areal(0), _areal(1), domain="impressed",
        reference_scores=scores, reference_labels=labels, reference_name="synthetic",
    )
    assert rep.domain == "impressed" and rep.score_kind == "cmr-2d"
    assert np.isfinite(rep.likelihood_ratio)
    assert isinstance(rep.attribution, list)  # CMR congruent regions (may be empty on noise)


def test_compare_with_previews_impressed_has_attribution_and_previews():
    from verity.compare import compare_with_previews

    scores, labels = _ref()
    report, previews = compare_with_previews(
        _areal(0), _areal(0), domain="impressed",  # identical -> strongly congruent
        reference_scores=scores, reference_labels=labels, reference_name="synthetic",
    )
    assert set(previews) == {"a", "b"} and len(previews["a"]) > 0
    assert len(report.attribution) > 0  # a mark vs itself is congruent everywhere
    region = report.attribution[0]
    assert {"x_frac", "y_frac", "w_frac", "h_frac", "corr"} <= set(region)


def test_unknown_domain_raises():
    with pytest.raises(ValueError, match="domain"):
        comparison_score(_striated(), _striated(), domain="footwear")


def test_compare_bullets_aggregates_lands():
    from verity.compare import compare_bullets

    bullet = [_striated(shift=k * 3) for k in range(4)]  # a 4-land "bullet"
    scores, labels = _ref()
    rep = compare_bullets(
        bullet,
        bullet,
        reference_scores=scores,
        reference_labels=labels,
        reference_name="synthetic",
    )
    assert rep.domain == "striated" and rep.score_kind == "bullet-contrast"
    assert np.isfinite(rep.likelihood_ratio)
    assert rep.provenance["n_lands_a"] == 4 and rep.provenance["n_lands_b"] == 4


def _bullet(seed: int, n: int = 4) -> list[Surface]:
    """A synthetic bullet: n lands, each a *distinct* vertical-striation surface."""
    from scipy.ndimage import gaussian_filter1d

    rng = np.random.default_rng(seed)
    return [
        Surface(
            heights=np.tile(gaussian_filter1d(rng.normal(size=400), 3.0), (60, 1)),
            dx=1e-6,
            dy=1e-6,
        )
        for _ in range(n)
    ]


def test_compare_bullets_scores_on_diag_contrast_not_diag_mean():
    """Regression: the bullet score must be ``diag_contrast`` (the margin the bullet
    reference is built on), NOT ``diag_mean``. Scoring on diag_mean put every live
    comparison above the reference and saturated the LR at the cap for any pair."""
    from verity.aggregate import bullet_comparison
    from verity.compare import compare_bullets
    from verity.decision import DEFAULT_SCORER_CONFIG as _CFG
    from verity.signature import striation_signature

    a, b = _bullet(0), _bullet(1)
    scores, labels = _ref()
    rep = compare_bullets(
        a, b, reference_scores=scores, reference_labels=labels, reference_name="syn"
    )
    sa = [striation_signature(s, lambda_s=_CFG.lambda_s, lambda_c=_CFG.lambda_c) for s in a]
    sb = [striation_signature(s, lambda_s=_CFG.lambda_s, lambda_c=_CFG.lambda_c) for s in b]
    cmp = bullet_comparison(sa, sb)
    assert rep.score_kind == "bullet-contrast"
    assert rep.score == pytest.approx(cmp.diag_contrast)


def test_config_override_default_invariance_and_effect():
    """Threading a per-request ScorerConfig must leave the deployed default path
    byte-identical (the safety guarantee), and an explicit override must change the score
    (the basis for the API's off-config calibration refusal)."""
    import dataclasses

    from verity.decision import DEFAULT_SCORER_CONFIG

    a, b = _striated(0), _striated(7)
    base, kind = comparison_score(a, b, domain="striated")
    assert kind == "ccf"
    assert comparison_score(a, b, domain="striated", config=DEFAULT_SCORER_CONFIG)[0] == base
    tight = dataclasses.replace(DEFAULT_SCORER_CONFIG, lambda_c=8e-6)
    assert comparison_score(a, b, domain="striated", config=tight)[0] != base

    # Impressed: the areal-band guard must keep the deployed band for the default config
    # (areal_signature's own lambda_c differs from the striated band).
    ia, ib = _areal(0), _areal(1)
    ibase = comparison_score(ia, ib, domain="impressed")[0]
    assert comparison_score(ia, ib, domain="impressed", config=DEFAULT_SCORER_CONFIG)[0] == ibase
