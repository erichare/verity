"""Synthetic tests for the Phase-4 toolmark transfer harness.

These exercise the dataset-independent core — mark-level pairwise scoring and the
source-disjoint Cllr evaluation — on synthetic marks, so the machinery is proven
before the real screwdriver X3P scans are wired in. (The X3P loader is a thin
glob + read + signature wrapper, exercised on the real data.)
"""

from __future__ import annotations

import numpy as np

from verity.examples.toolmark_transfer import (
    evaluate,
    mark_pairwise_scores,
    profile_signature,
)


def _synthetic_marks(n_sources: int = 6, n_rep: int = 5, length: int = 300, seed: int = 0):
    """Each source = a distinct multi-sinusoid striation; replicates add a random
    circular shift + noise (what align_1d must see through)."""
    rng = np.random.default_rng(seed)
    x = np.arange(length)
    marks = []
    for s in range(n_sources):
        freqs = rng.uniform(0.03, 0.2, size=4)
        phases = rng.uniform(0, 2 * np.pi, size=4)
        base = sum(np.sin(2 * np.pi * f * x + p) for f, p in zip(freqs, phases, strict=True))
        base = (base - base.mean()) / (base.std() + 1e-9)
        for r in range(n_rep):
            shift = int(rng.integers(-20, 21))
            sig = np.roll(base, shift) + rng.normal(0, 0.15, size=length)
            marks.append((f"tool{s}", f"tool{s}_m{r}", sig))
    return marks


def test_same_source_marks_score_higher():
    scores, labels, sa, sb = mark_pairwise_scores(_synthetic_marks())
    assert len(scores) > 0
    assert labels.sum() > 0 and (labels == 0).sum() > 0
    km = scores[labels == 1].mean()
    knm = scores[labels == 0].mean()
    assert km > knm + 0.3  # same-tool marks correlate, different tools don't


def test_source_disjoint_transfer_is_informative():
    res = evaluate(_synthetic_marks())
    assert res["n_sources"] == 6
    assert res["folds"], "expected at least one source-disjoint fold"
    mean_cllr = np.mean([f["cllr"] for f in res["folds"]])
    assert mean_cllr < 0.5  # informative calibrated LRs across held-out tools


def test_profile_signature_recovers_striae_from_form():
    """A profile dominated by form/waviness: the signature must isolate the
    striae (high correlation) and shed the form (which raw cross-correlation
    would otherwise lock onto)."""
    x = np.arange(4000)
    form = 50.0 * (x / 4000.0 - 0.5) ** 2  # large curvature
    striae = np.sin(2 * np.pi * x / 25.0)  # the individualizing band
    profile = form + 0.3 * striae + np.random.default_rng(0).normal(0, 0.02, len(x))

    sig = profile_signature(profile, waviness=80.0)
    assert len(sig) == len(x)
    # signature tracks the striae, not the form
    assert abs(np.corrcoef(sig, striae)[0, 1]) > 0.9
    assert abs(np.corrcoef(sig, form)[0, 1]) < 0.2


def test_label_shuffle_collapses_to_chance():
    """Skeptic-killer: shuffling source labels must destroy the signal (Cllr -> ~1)."""
    marks = _synthetic_marks()
    rng = np.random.default_rng(1)
    sources = [m[0] for m in marks]
    rng.shuffle(sources)
    shuffled = [(src, m[1], m[2]) for src, m in zip(sources, marks, strict=True)]
    res = evaluate(shuffled)
    if res["folds"]:
        assert np.mean([f["cllr"] for f in res["folds"]]) > 0.8
