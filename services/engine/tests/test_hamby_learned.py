"""Data-gated Phase-2b experiment: the learned representation vs CCF, barrel-disjoint.

This asserts the experiment *runs* and the CCF baseline is strong — NOT that the
learned representation wins. On 210 scans it does not (it overfits across
barrels); the synthetic ``test_representation`` tests show the pipeline learns
when given enough signal, so this is a data limit, not a code defect.

Opt in with ``VERITY_HAMBY_TEST=1``.
"""

import os

import pytest

pytest.importorskip("verity_x3p")
pytest.importorskip("verity_catalog")
pytest.importorskip("torch")


@pytest.mark.skipif(
    not os.environ.get("VERITY_HAMBY_TEST"),
    reason="set VERITY_HAMBY_TEST=1 after ingesting the hamby-252 manifest",
)
def test_learned_vs_ccf_experiment_runs():
    import numpy as np

    from verity.examples.hamby_learned import evaluate

    res = evaluate(n_splits=3)
    assert res["n_bullets"] >= 30
    folds = res["folds"]
    assert len(folds) >= 2
    for fold in folds:
        for system in ("ccf", "learned"):
            assert np.isfinite(fold[system]["cllr"])
            assert np.isfinite(fold[system]["auc"])
    # The CCF baseline discriminates strongly — confirms the harness is sound.
    assert float(np.mean([f["ccf"]["auc"] for f in folds])) > 0.8
