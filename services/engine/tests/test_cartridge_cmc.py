"""Tests for the Verity-vs-CMC join logic (no R needed)."""

from __future__ import annotations

import numpy as np

from verity.examples.cartridge_cmc_proof import _aligned


def _marks():
    rng = np.random.default_rng(0)

    def m(seed):
        z = rng.normal(size=(32, 32))
        z -= z.mean()
        return z / (np.linalg.norm(z) + 1e-12)

    return [(1, "1-1", m(0)), (1, "1-2", m(1)), (2, "2-1", m(2))]  # slides 1,1,2


def test_aligned_joins_labels_and_drops_na():
    marks = _marks()
    cmc_rows = [
        {"i": "0", "j": "1", "cmc": "18", "slide_i": "1", "slide_j": "1"},  # KM
        {"i": "0", "j": "2", "cmc": "2", "slide_i": "1", "slide_j": "2"},  # KNM
        {"i": "1", "j": "2", "cmc": "NA", "slide_i": "1", "slide_j": "2"},  # dropped
    ]
    v, c, y, ga, gb = _aligned(marks, cmc_rows)
    assert len(v) == len(c) == len(y) == 2  # the NA pair dropped
    assert c.tolist() == [18.0, 2.0]
    assert y.tolist() == [1, 0]  # same-slide -> KM, different-slide -> KNM


def test_aligned_skips_ordering_mismatch():
    marks = _marks()
    # slide_i claims 2 but marks[0] is slide 1 -> guard should skip this row
    bad = [{"i": "0", "j": "1", "cmc": "5", "slide_i": "2", "slide_j": "1"}]
    v, _c, _y, _ga, _gb = _aligned(marks, bad)
    assert len(v) == 0
