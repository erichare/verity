"""Tests for the bootstrap credible interval on the calibrated LR."""

from __future__ import annotations

import json
import logging

import numpy as np
import pytest

from verity.decision import uncertainty
from verity.decision.uncertainty import (
    BootstrapCalibration,
    cached_bootstrap_calibration,
    default_n_boot,
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


# --- the VERITY_LR_BOOTSTRAP_N knob ------------------------------------------


def test_default_n_boot_env_knob(monkeypatch):
    monkeypatch.delenv("VERITY_LR_BOOTSTRAP_N", raising=False)
    monkeypatch.delenv("VERITY_ENSEMBLE_CACHE_DIR", raising=False)
    assert default_n_boot() == 1000
    monkeypatch.setenv("VERITY_LR_BOOTSTRAP_N", "25")
    assert default_n_boot() == 25
    # threads through everywhere n_boot is left unspecified
    scores, labels = _reference()
    cal = cached_bootstrap_calibration(scores, labels, seed=11)
    assert cal.n_boot == 25


def test_default_n_boot_rejects_malformed_values(monkeypatch):
    for bad in ("abc", "0", "-5"):
        monkeypatch.setenv("VERITY_LR_BOOTSTRAP_N", bad)
        with pytest.raises(ValueError, match="VERITY_LR_BOOTSTRAP_N"):
            default_n_boot()


# --- the VERITY_ENSEMBLE_CACHE_DIR disk cache ---------------------------------


def _forbid_refit(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("expected a disk-cache hit, but a refit happened")

    monkeypatch.setattr(BootstrapCalibration, "fit", boom)


def test_disk_cache_restores_identical_ensemble(monkeypatch, tmp_path):
    monkeypatch.setenv("VERITY_ENSEMBLE_CACHE_DIR", str(tmp_path))
    scores, labels = _reference()
    uncertainty._ENSEMBLE_CACHE.clear()
    fresh = lr_credible_interval(scores, labels, 1.0, n_boot=60, seed=9)
    assert len(list(tmp_path.glob("*.npz"))) == 1
    # a "fresh process": empty in-memory cache, and refitting forbidden
    uncertainty._ENSEMBLE_CACHE.clear()
    _forbid_refit(monkeypatch)
    warm = lr_credible_interval(scores, labels, 1.0, n_boot=60, seed=9)
    # LRInterval is a frozen dataclass: == compares every field, so the restored
    # ensemble reproduces the cold fit exactly — the audit property of the cache.
    assert warm == fresh


def test_disk_cache_roundtrip_clustered(monkeypatch, tmp_path):
    # clustered + "auto" bound → the resolved bound varies per replicate; the
    # cache must restore each replicate's own bound, not one shared value
    monkeypatch.setenv("VERITY_ENSEMBLE_CACHE_DIR", str(tmp_path))
    scores, labels, clusters = _clustered_reference()
    uncertainty._ENSEMBLE_CACHE.clear()
    fresh = lr_credible_interval(scores, labels, 0.0, n_boot=80, seed=13, cluster_ids=clusters)
    uncertainty._ENSEMBLE_CACHE.clear()
    _forbid_refit(monkeypatch)
    warm = lr_credible_interval(scores, labels, 0.0, n_boot=80, seed=13, cluster_ids=clusters)
    assert warm == fresh
    assert warm.resample == "clustered"
    assert warm.n_sources == 16


def test_disk_cache_corrupt_entry_falls_back_to_refit(monkeypatch, tmp_path, caplog):
    monkeypatch.setenv("VERITY_ENSEMBLE_CACHE_DIR", str(tmp_path))
    scores, labels = _reference()
    uncertainty._ENSEMBLE_CACHE.clear()
    fresh = lr_credible_interval(scores, labels, 1.0, n_boot=40, seed=17)
    (entry,) = tmp_path.glob("*.npz")
    entry.write_bytes(b"not an npz")
    uncertainty._ENSEMBLE_CACHE.clear()
    with caplog.at_level(logging.WARNING, logger="verity.decision.uncertainty"):
        refit = lr_credible_interval(scores, labels, 1.0, n_boot=40, seed=17)
    assert refit == fresh  # fixed seed → the refit reproduces the same ensemble
    assert "ignoring unreadable" in caplog.text
    # the refit overwrote the corrupt entry, so the next process loads cleanly
    uncertainty._ENSEMBLE_CACHE.clear()
    _forbid_refit(monkeypatch)
    assert lr_credible_interval(scores, labels, 1.0, n_boot=40, seed=17) == fresh


def test_ensemble_key_canonicalizes_cluster_labels():
    # the key hashes canonical inverse codes, so labellings the fit cannot tell
    # apart key identically — a dtype or naming change must not silently miss the
    # (now persistent) cache
    scores, labels, clusters = _clustered_reference()
    key = uncertainty._ensemble_key
    base = key(scores, labels, "logistic", "auto", 100, 0, clusters.astype(np.int64))
    assert key(scores, labels, "logistic", "auto", 100, 0, clusters.astype(np.int32)) == base
    # zero-padded strings sort like the ints → same resampling → same key
    padded = np.array([f"src-{c:02d}" for c in clusters])
    assert key(scores, labels, "logistic", "auto", 100, 0, padded) == base
    # but a labelling the resampler would draw differently keys differently
    other = np.roll(clusters, len(clusters) // 2)
    assert key(scores, labels, "logistic", "auto", 100, 0, other) != base


def test_disk_cache_skips_isotonic(monkeypatch, tmp_path):
    # isotonic state is variable-length and only used diagnostically — it stays
    # in-memory only, and nothing lands on disk
    monkeypatch.setenv("VERITY_ENSEMBLE_CACHE_DIR", str(tmp_path))
    scores, labels = _reference()
    uncertainty._ENSEMBLE_CACHE.clear()
    cal = cached_bootstrap_calibration(scores, labels, method="isotonic", n_boot=20, seed=19)
    assert cal.n_boot == 20
    assert list(tmp_path.glob("*.npz")) == []
