"""Cross-instrument stratification logic — pure over an injected score function,
so the within/cross bucketing and the per-stratum summary are tested without the
real areal scorer or any catalog data (areal_score itself is covered in
test_areal.py)."""

import numpy as np

from verity.examples.cross_instrument import stratified_pairs, summarize_stratum


def _marks():
    """6 firearms x 2 instruments x 2 replicate scans; sig encodes the firearm."""
    return [
        (fid, inst, float(fid)) for fid in range(1, 7) for inst in ("A", "B") for _rep in range(2)
    ]


# A perfect same-source separator: 1.0 when the two specimens share a firearm.
def _perfect(a, b):
    return 1.0 if a == b else 0.0


def test_stratified_pairs_buckets_by_instrument():
    strata = stratified_pairs(_marks(), _perfect)  # 24 marks -> C(24,2)=276 pairs
    within, cross = strata["within"], strata["cross"]
    # 12 scans per instrument: within = 2*C(12,2) = 132, cross = 12*12 = 144
    assert len(within[0]) == 132
    assert len(cross[0]) == 144
    assert len(within[0]) + len(cross[0]) == 276
    # KM = same firearm: within has 1 same-instrument pair per firearm per side (12),
    # cross has 2x2 across-instrument same-firearm pairs per firearm (24).
    assert int(within[1].sum()) == 12
    assert int(cross[1].sum()) == 24
    # source arrays are aligned with scores/labels
    assert len(within[2]) == len(within[3]) == len(within[0])


def test_summarize_stratum_metrics_and_folds():
    within = stratified_pairs(_marks(), _perfect)["within"]
    s = summarize_stratum(within)
    assert s["pairs"] == 132 and s["km"] == 12 and s["knm"] == 120
    assert s["auc"] == 1.0  # KM=1.0, KNM=0.0 -> perfect discrimination
    assert np.isfinite(s["cllr_min"])
    assert isinstance(s["folds"], list)


def test_summarize_single_class_is_safe():
    # one instrument, all distinct firearms -> only KNM pairs; metrics degrade to
    # NaN and no folds, without calling the metrics on a single-class set.
    marks = [(1, "A", 1.0), (2, "A", 2.0), (3, "A", 3.0)]
    s = summarize_stratum(stratified_pairs(marks, _perfect)["within"])
    assert s["pairs"] == 3 and s["km"] == 0
    assert np.isnan(s["auc"]) and np.isnan(s["cllr_min"])
    assert s["folds"] == []
