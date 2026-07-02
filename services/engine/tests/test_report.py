"""Tests for the comparison-report contract."""

from __future__ import annotations

import json

import numpy as np

from verity.report import ComparisonReport, build_comparison_report, verbal_weight


def test_verbal_weight_bands_and_direction():
    assert "no meaningful" in verbal_weight(0.0)
    assert verbal_weight(0.5) == "weak or limited support for same source"
    assert verbal_weight(1.5) == "moderate support for same source"
    assert verbal_weight(2.5) == "moderately strong support for same source"
    assert verbal_weight(-3.5) == "strong support for different sources"
    assert verbal_weight(7.0) == "extremely strong support for same source"


def _reference(seed=0):
    rng = np.random.default_rng(seed)
    km = rng.normal(3, 1, 60)
    knm = rng.normal(-1, 1, 240)
    scores = np.concatenate([km, knm])
    labels = np.concatenate([np.ones(60), np.zeros(240)])
    return scores, labels


def test_report_same_source_score():
    scores, labels = _reference()
    rep = build_comparison_report(
        score=3.5, reference_scores=scores, reference_labels=labels,
        domain="bullet land", reference_name="Hamby-252", score_kind="ccf",
        provenance={"engine": "test"},
    )
    assert isinstance(rep, ComparisonReport)
    assert rep.likelihood_ratio > 1.0 and rep.log10_lr > 0
    assert rep.direction == "same source"
    assert "same source" in rep.verbal
    assert rep.reference["name"] == "Hamby-252" and rep.reference["auc"] > 0.9
    assert rep.lr_bound_log10 is not None  # ELUB bound applied
    assert "It is not a verdict" in rep.scope_note
    assert "not a claim about the error rate" in rep.scope_note


def test_report_different_source_score_and_json():
    scores, labels = _reference()
    rep = build_comparison_report(
        score=-2.0, reference_scores=scores, reference_labels=labels,
        domain="bullet land", reference_name="Hamby-252",
        attribution=[{"region": [10, 20], "contribution": 0.8}],
    )
    assert rep.likelihood_ratio < 1.0 and rep.direction == "different sources"
    # the whole payload must be JSON-serializable (the API serves it verbatim)
    blob = json.dumps(rep.to_dict())
    assert "scope_note" in blob and "attribution" in blob


def test_lr_is_bounded_by_reference_size():
    scores, labels = _reference()
    rep = build_comparison_report(
        score=99.0, reference_scores=scores, reference_labels=labels,  # absurdly high
        domain="bullet land", reference_name="Hamby-252",
    )
    assert rep.log10_lr <= rep.lr_bound_log10 + 1e-9  # cannot exceed what the data supports


def test_lr_bound_hit_flags_a_clipped_lr():
    scores, labels = _reference()
    rep = build_comparison_report(
        score=99.0, reference_scores=scores, reference_labels=labels,  # absurdly high
        domain="bullet land", reference_name="Hamby-252", ci=False,
    )
    assert rep.lr_bound_hit is True  # pre-cap LR exceeded the bound -> clipped to it
    assert abs(abs(rep.log10_lr) - rep.lr_bound_log10) < 1e-9  # sits exactly AT the cap
    assert "bound-limited" in rep.scope_note
    assert rep.to_dict()["lr_bound_hit"] is True  # rides along in the served payload


def test_lr_bound_hit_false_for_a_measured_lr():
    scores, labels = _reference()
    rep = build_comparison_report(
        score=1.0, reference_scores=scores, reference_labels=labels,  # class overlap
        domain="bullet land", reference_name="Hamby-252", ci=False,
    )
    assert rep.lr_bound_hit is False
    assert abs(rep.log10_lr) < rep.lr_bound_log10  # strictly inside the bound
    assert "bound-limited" not in rep.scope_note
