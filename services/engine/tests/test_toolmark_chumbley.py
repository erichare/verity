"""Tests for the Verity-vs-Chumbley join logic (no R needed)."""

from __future__ import annotations

import numpy as np

from verity.examples.toolmark_chumbley_proof import _aligned_arrays, verity_pair_scores


def _marks():
    rng = np.random.default_rng(0)
    bases = {t: rng.normal(0, 1, 200) for t in ("A", "B", "C")}
    marks = []
    for t in ("A", "B", "C"):
        for r in range(2):
            marks.append((t, f"{t}{r}", bases[t] + rng.normal(0, 0.05, 200)))
    return marks  # 6 marks, 3 tools, 2 reps each


def test_verity_pair_scores_keys_and_labels():
    marks = _marks()
    vp = verity_pair_scores(marks)
    assert len(vp) == 6 * 5 // 2  # all unordered pairs
    # within-tool pairs are labelled KM, across-tool KNM
    for (i, j), (_cc, label, ta, tb) in vp.items():
        assert i < j
        assert label == (1 if ta == tb else 0)


def test_aligned_arrays_joins_and_drops_na():
    marks = _marks()
    vp = verity_pair_scores(marks)
    # build a Chumbley table for the same pairs, with one NA that must be dropped
    chumbley = []
    for n, (i, j) in enumerate(vp):
        _cc, _label, ta, tb = vp[(i, j)]
        u = "NA" if n == 0 else f"{1.0 if ta == tb else 0.0}"
        chumbley.append({"i": str(i), "j": str(j), "U": u, "id_i": ta, "id_j": tb})
    v, c, y, taa, tbb = _aligned_arrays(marks, chumbley)
    assert len(v) == len(vp) - 1  # the NA pair dropped
    assert len(c) == len(y) == len(taa) == len(tbb) == len(v)
    assert set(np.unique(y)).issubset({0, 1})
