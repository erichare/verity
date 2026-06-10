"""The frozen-benchmark contract: pair identity, fold freezing, split hashing,
LOSO calibration, and submission scoring."""

from __future__ import annotations

import numpy as np
import pytest

from verity.benchmark import (
    freeze_folds,
    loso_lrs,
    make_pair,
    mark_hash,
    pair_id,
    score_submission,
    split_hash,
    validate_submission_lrs,
)


def _hash(i: int) -> str:
    return f"{i:064x}"


def _synthetic_pairs(n_sources: int = 8, marks_per_source: int = 3, seed: int = 7):
    """Fully-enumerated synthetic split: KM scores ~ N(1, .3), KNM ~ N(0, .3)."""
    rng = np.random.default_rng(seed)
    marks = [
        (f"src{s}", _hash(s * marks_per_source + k))
        for s in range(n_sources)
        for k in range(marks_per_source)
    ]
    pairs, scores = [], []
    for i in range(len(marks)):
        for j in range(i + 1, len(marks)):
            (sa, ha), (sb, hb) = marks[i], marks[j]
            label = 1 if sa == sb else 0
            pairs.append(make_pair(ha, hb, label, sa, sb))
            scores.append(rng.normal(1.0 if label else 0.0, 0.3))
    return pairs, np.array(scores)


# --------------------------------------------------------------------------- #
# Identity hashing
# --------------------------------------------------------------------------- #
def test_pair_id_is_order_independent():
    assert pair_id(_hash(1), _hash(2)) == pair_id(_hash(2), _hash(1))
    assert pair_id(_hash(1), _hash(2)) != pair_id(_hash(1), _hash(3))


def test_mark_hash_single_scan_is_the_scan_hash():
    assert mark_hash([_hash(5)]) == _hash(5)


def test_mark_hash_multi_scan_is_order_independent():
    a = mark_hash([_hash(1), _hash(2), _hash(3)])
    b = mark_hash([_hash(3), _hash(1), _hash(2)])
    assert a == b
    assert a != _hash(1) and len(a) == 64


def test_make_pair_canonicalizes_and_keeps_sources_attached():
    p = make_pair(_hash(9), _hash(1), 0, "src-of-9", "src-of-1")
    assert p.hash_a == _hash(1) and p.hash_b == _hash(9)
    assert p.source_a == "src-of-1" and p.source_b == "src-of-9"


# --------------------------------------------------------------------------- #
# Fold freezing
# --------------------------------------------------------------------------- #
def test_freeze_folds_is_deterministic_and_source_disjoint():
    pairs, _ = _synthetic_pairs()
    folds_1 = freeze_folds(pairs, seed=0)
    folds_2 = freeze_folds(pairs, seed=0)
    assert folds_1 == folds_2
    assert len(folds_1) > 0
    for fold in folds_1:
        held_out = set(fold.test_sources)
        for idx in fold.pair_indices:
            assert pairs[idx].source_a in held_out
            assert pairs[idx].source_b in held_out


def test_freeze_folds_seed_changes_folds():
    pairs, _ = _synthetic_pairs()
    assert freeze_folds(pairs, seed=0) != freeze_folds(pairs, seed=1)


# --------------------------------------------------------------------------- #
# Split hash
# --------------------------------------------------------------------------- #
def test_split_hash_commits_to_labels_and_folds():
    pairs, _ = _synthetic_pairs()
    folds = freeze_folds(pairs)
    base = split_hash(pairs, folds)
    assert base == split_hash(pairs, folds)  # stable

    flipped = list(pairs)
    p = flipped[0]
    flipped[0] = make_pair(p.hash_a, p.hash_b, 1 - p.label, p.source_a, p.source_b)
    assert split_hash(flipped, folds) != base

    assert split_hash(pairs, folds[:-1]) != base  # fold structure is committed too


# --------------------------------------------------------------------------- #
# LOSO calibration
# --------------------------------------------------------------------------- #
def test_loso_lrs_are_finite_and_directionally_sane():
    pairs, scores = _synthetic_pairs()
    lrs = loso_lrs(scores, pairs)
    assert np.isfinite(lrs).all()
    labels = np.array([p.label for p in pairs])
    assert np.median(lrs[labels == 1]) > 1.0 > np.median(lrs[labels == 0])


def test_loso_excludes_the_pairs_sources_from_calibration():
    """Perturbing every score that involves the pair's sources must not change
    that pair's LR — those pairs are outside its calibration set."""
    pairs, scores = _synthetic_pairs()
    target = next(i for i, p in enumerate(pairs) if p.label == 0)
    excluded = {pairs[target].source_a, pairs[target].source_b}
    touched = np.array(
        [p.source_a in excluded or p.source_b in excluded for p in pairs]
    )
    perturbed = scores.copy()
    perturbed[touched & (np.arange(len(pairs)) != target)] += 5.0

    lr_base = loso_lrs(scores, pairs)[target]
    lr_perturbed = loso_lrs(perturbed, pairs)[target]
    assert lr_base == pytest.approx(lr_perturbed)


def test_loso_starved_groups_are_nan():
    # Two sources only: excluding both leaves nothing to calibrate on.
    pairs = [
        make_pair(_hash(1), _hash(2), 1, "a", "a"),
        make_pair(_hash(3), _hash(4), 1, "b", "b"),
        make_pair(_hash(1), _hash(3), 0, "a", "b"),
    ]
    lrs = loso_lrs(np.array([1.0, 1.1, 0.1]), pairs)
    assert np.isnan(lrs).all()


# --------------------------------------------------------------------------- #
# Submission scoring
# --------------------------------------------------------------------------- #
def test_score_submission_rewards_good_lrs():
    pairs, scores = _synthetic_pairs()
    folds = freeze_folds(pairs)
    metrics = score_submission(loso_lrs(scores, pairs), pairs, folds)
    assert 0.0 < metrics["cllr"] < 1.0
    assert metrics["auc"] > 0.8
    assert metrics["calibration_loss"] == pytest.approx(
        metrics["cllr"] - metrics["cllr_min"]
    )
    assert metrics["pooled"]["n_pairs"] == len(pairs)
    assert metrics["n_folds"] == len(folds)


def test_score_submission_label_shuffle_is_uninformative():
    """An LR assignment carrying no information about the labels scores ~1."""
    pairs, scores = _synthetic_pairs()
    folds = freeze_folds(pairs)
    rng = np.random.default_rng(3)
    junk = 10.0 ** rng.normal(0.0, 0.5, len(pairs))
    metrics = score_submission(junk, pairs, folds)
    assert metrics["cllr"] > 0.8


def test_score_submission_rejects_junk_lrs():
    pairs, _ = _synthetic_pairs()
    folds = freeze_folds(pairs)
    bad = np.ones(len(pairs))
    bad[0] = -1.0
    with pytest.raises(ValueError, match="strictly positive"):
        score_submission(bad, pairs, folds)
    bad[0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        score_submission(bad, pairs, folds)
    assert validate_submission_lrs(np.ones(3)) == []
