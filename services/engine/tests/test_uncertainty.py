"""Tests for the bootstrap credible interval on the calibrated LR."""

from __future__ import annotations

import json

import numpy as np

from verity.decision.uncertainty import (
    BootstrapCalibration,
    lr_credible_interval,
)
from verity.report import build_comparison_report


def _reference(seed: int = 0, n_km: int = 80, n_knm: int = 320):
    """A well-separated synthetic reference: KM ~ N(3,1), KNM ~ N(-1,1).

    Balanced calibration puts the decision boundary at the means' midpoint
    (score ≈ 1.0), so a query at 1.0 gives log10 LR ≈ 0."""
    rng = np.random.default_rng(seed)
    km = rng.normal(3.0, 1.0, n_km)
    knm = rng.normal(-1.0, 1.0, n_knm)
    scores = np.concatenate([km, knm])
    labels = np.concatenate([np.ones(n_km), np.zeros(n_knm)])
    return scores, labels


def test_interval_is_ordered_and_brackets_point():
    scores, labels = _reference()
    iv = lr_credible_interval(scores, labels, 1.0, n_boot=200, seed=1)
    assert iv.lo_log10_lr <= iv.hi_log10_lr
    assert iv.lo_log10_lr - 1e-9 <= iv.point_log10_lr <= iv.hi_log10_lr + 1e-9
    assert iv.resample == "row-stratified"
    assert iv.n_sources is None


def test_interval_respects_elub_cap():
    scores, labels = _reference()
    bound = float(np.log10(80))  # log10(max(n_minority, 10)) = log10(80)
    iv = lr_credible_interval(scores, labels, 50.0, n_boot=150, seed=2)  # absurdly high score
    assert iv.hi_log10_lr <= bound + 1e-9
    assert iv.lo_log10_lr >= -bound - 1e-9
    assert iv.point_log10_lr <= bound + 1e-9


def test_straddle_zero_detection():
    scores, labels = _reference()
    # score at the boundary → evidence direction unresolved
    straddle = lr_credible_interval(scores, labels, 1.0, n_boot=200, seed=3)
    assert straddle.straddles_zero
    # a strongly same-source score → resolved, positive
    strong = lr_credible_interval(scores, labels, 3.0, n_boot=200, seed=3)
    assert not strong.straddles_zero
    assert strong.lo_log10_lr > 0.0


def _clustered_reference(seed: int = 3, rows_per: int = 15):
    """Sources with identical within-cluster scores: a row bootstrap treats the
    rows as independent (narrow), a clustered bootstrap resamples the few sources
    (wide). 4 KM clusters + 12 KNM clusters."""
    rng = np.random.default_rng(seed)
    scores: list[float] = []
    labels: list[int] = []
    clusters: list[int] = []
    cid = 0
    for _ in range(4):
        val = float(rng.normal(2.5, 0.5))
        scores += [val] * rows_per
        labels += [1] * rows_per
        clusters += [cid] * rows_per
        cid += 1
    for _ in range(12):
        val = float(rng.normal(-2.0, 0.5))
        scores += [val] * rows_per
        labels += [0] * rows_per
        clusters += [cid] * rows_per
        cid += 1
    return np.array(scores), np.array(labels), np.array(clusters)


def test_clustered_interval_not_narrower_than_row():
    scores, labels, clusters = _clustered_reference()
    row = lr_credible_interval(scores, labels, 0.0, n_boot=300, seed=5)
    clu = lr_credible_interval(scores, labels, 0.0, n_boot=300, seed=5, cluster_ids=clusters)
    assert clu.resample == "clustered"
    assert clu.n_sources == 16
    row_width = row.hi_log10_lr - row.lo_log10_lr
    clu_width = clu.hi_log10_lr - clu.lo_log10_lr
    assert clu_width >= row_width


def test_bootstrap_calibration_reuses_ensemble():
    scores, labels = _reference()
    cal = BootstrapCalibration.fit(scores, labels, n_boot=120, seed=7)
    a = cal.interval(3.0, point_log10_lr=1.5)
    b = cal.interval(-2.0, point_log10_lr=-1.5)
    # one ensemble answers different queries; a same-source score outweighs a
    # different-source one
    assert a.hi_log10_lr > b.hi_log10_lr


def test_report_carries_ci_and_widens_verbal_on_straddle():
    scores, labels = _reference()
    rep = build_comparison_report(
        score=1.0,  # boundary → straddles zero
        reference_scores=scores,
        reference_labels=labels,
        domain="bullet land",
        reference_name="synthetic",
        ci_n_boot=200,
    )
    assert rep.log10_lr_ci_lo is not None and rep.log10_lr_ci_hi is not None
    assert rep.lr_ci_method == "bootstrap-row-stratified"
    assert rep.log10_lr_ci_lo <= rep.log10_lr <= rep.log10_lr_ci_hi
    assert "direction not resolved" in rep.verbal
    # the whole payload stays JSON-serializable
    blob = json.dumps(rep.to_dict())
    assert "log10_lr_ci_lo" in blob


def test_report_ci_can_be_disabled():
    scores, labels = _reference()
    rep = build_comparison_report(
        score=3.0,
        reference_scores=scores,
        reference_labels=labels,
        domain="bullet land",
        reference_name="synthetic",
        ci=False,
    )
    assert rep.log10_lr_ci_lo is None
    assert rep.log10_lr_ci_hi is None
    assert rep.lr_ci_method is None
