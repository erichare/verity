"""Data-gated sanity anchor on the real Hamby 252 set.

Requires the ``hamby-252`` manifest ingested into the catalog (~733 MB) and the
``demo`` extra installed. Opt in with ``VERITY_HAMBY_TEST=1`` so the normal
suite stays fast and CI (which has no data) skips it.
"""

import os

import pytest

pytest.importorskip("verity_x3p")
pytest.importorskip("verity_catalog")


@pytest.mark.skipif(
    not os.environ.get("VERITY_HAMBY_TEST"),
    reason="set VERITY_HAMBY_TEST=1 after ingesting the hamby-252 manifest",
)
def test_km_beats_knm_on_hamby():
    import numpy as np

    from verity.examples.hamby_km_knm import evaluate

    res = evaluate()
    km, knm = res["km"], res["knm"]
    assert len(km) >= 5 and len(knm) >= 10
    # The Phase-1 preprocessing + orientation + 1-D registration produce a signal
    # that scores same-barrel (KM) bullet pairs above different-barrel (KNM) pairs.
    assert float(np.mean(km)) > float(np.mean(knm))
