"""The numpy-only benchmark scorer — engine parity (pinned constants) and the
submission-scoring contract."""

from __future__ import annotations

import numpy as np
import pytest

from verity_catalog.benchmark import scoring


# --------------------------------------------------------------------------- #
# Engine parity — constants computed by verity.decision (sklearn paths) on the
# exact same arrays; regenerate with services/engine if semantics ever change.
# --------------------------------------------------------------------------- #
def _pinned_arrays():
    rng = np.random.default_rng(7)
    labels = (rng.random(120) < 0.4).astype(float)
    scores = np.round(rng.normal(labels, 0.6), 2)
    lrs = 10 ** rng.normal(labels - 0.5, 0.8)
    return scores, labels, lrs


def test_cllr_min_matches_engine_pinned():
    scores, labels, _ = _pinned_arrays()
    assert scoring.cllr_min(scores, labels) == pytest.approx(0.5053978398975797, abs=1e-12)


def test_roc_auc_matches_engine_pinned():
    scores, labels, _ = _pinned_arrays()
    assert scoring.roc_auc(scores, labels) == pytest.approx(0.8947828621393179, abs=1e-12)


def test_cllr_matches_engine_pinned():
    _, labels, lrs = _pinned_arrays()
    assert scoring.cllr(lrs[labels == 1], lrs[labels == 0]) == pytest.approx(
        0.6608388053854914, abs=1e-12
    )


def test_ece_matches_engine_pinned():
    _, labels, lrs = _pinned_arrays()
    assert scoring.ece(lrs[labels == 1], lrs[labels == 0]) == pytest.approx(
        0.10246420567321834, abs=1e-12
    )


# --------------------------------------------------------------------------- #
# Behavioral sanity
# --------------------------------------------------------------------------- #
def test_pav_fit_is_monotone_in_score():
    rng = np.random.default_rng(0)
    scores = rng.normal(size=200)
    labels = (rng.random(200) < 1 / (1 + np.exp(-2 * scores))).astype(float)
    fitted = scoring._pav_fit(scores, labels)
    order = np.argsort(scores)
    assert np.all(np.diff(fitted[order]) >= -1e-12)


def test_perfect_separation_floors_cllr_min():
    scores = np.array([0.0, 0.1, 0.2, 0.8, 0.9, 1.0])
    labels = np.array([0, 0, 0, 1, 1, 1], dtype=float)
    assert scoring.cllr_min(scores, labels) < 0.01
    assert scoring.roc_auc(scores, labels) == 1.0


def test_roc_auc_all_ties_is_half():
    assert scoring.roc_auc(np.ones(10), np.array([1, 0] * 5, dtype=float)) == 0.5


def test_validate_lrs():
    assert scoring.validate_lrs(np.array([1.0, 2.0])) == []
    assert any("positive" in p for p in scoring.validate_lrs(np.array([1.0, 0.0])))
    assert any("finite" in p for p in scoring.validate_lrs(np.array([1.0, np.inf])))


def test_score_submission_shape_and_headline():
    rng = np.random.default_rng(1)
    labels = np.array([1] * 20 + [0] * 80, dtype=float)
    lrs = 10 ** rng.normal(2 * labels - 1, 0.5)
    folds = [(k, np.arange(k, 100, 4)) for k in range(4)]
    m = scoring.score_submission(lrs, labels, folds)
    assert m["n_folds"] == 4
    assert m["calibration_loss"] == pytest.approx(m["cllr"] - m["cllr_min"])
    assert set(m["pooled"]) == {"n_pairs", "n_km", "n_knm", "cllr", "cllr_min", "auc", "ece"}
    assert m["auc"] > 0.9


def test_score_submission_rejects_junk():
    labels = np.array([1, 0, 1, 0], dtype=float)
    folds = [(0, np.arange(4))]
    with pytest.raises(ValueError, match="positive"):
        scoring.score_submission(np.array([1.0, -2.0, 1.0, 1.0]), labels, folds)
