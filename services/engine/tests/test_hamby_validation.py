"""Data-gated Phase-2 validation on the real Hamby 252 set.

Requires the ``hamby-252`` manifest ingested (~733 MB) and the ``demo`` extra.
Opt in with ``VERITY_HAMBY_TEST=1`` so the normal suite stays fast.
"""

import os

import pytest

pytest.importorskip("verity_x3p")
pytest.importorskip("verity_catalog")
pytest.importorskip("sklearn")


@pytest.mark.skipif(
    not os.environ.get("VERITY_HAMBY_TEST"),
    reason="set VERITY_HAMBY_TEST=1 after ingesting the hamby-252 manifest",
)
def test_hamby_barrel_disjoint_cllr_is_informative():
    import numpy as np

    from verity import cllr_min, roc_auc
    from verity.examples.hamby_validation import evaluate

    res = evaluate()
    assert res["n_bullets"] >= 30
    scores, labels = res["scores"], res["labels"]

    # Strong discrimination (the Phase-1 pipeline separates KM from KNM).
    assert roc_auc(scores, labels) > 0.8
    assert cllr_min(scores, labels) < 0.7

    folds = res["folds"]
    assert len(folds) >= 5
    mean_auc = float(np.mean([f["auc"] for f in folds]))
    mean_cllr = float(np.mean([f["cllr"] for f in folds]))
    # Discrimination holds out-of-sample, and the calibrated LRs stay informative
    # (Cllr < 1) under a source-disjoint (barrel-disjoint) protocol.
    assert mean_auc > 0.8
    assert mean_cllr < 0.85
