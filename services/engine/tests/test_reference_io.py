"""The shared reference writer: npz (scores/labels/cluster IDs) + provenance sidecar."""

from __future__ import annotations

import json

import numpy as np

from verity.decision import DEFAULT_SCORER_CONFIG
from verity.examples._reference_io import reference_diagnostics, write_reference


def _synth():
    rng = np.random.default_rng(0)
    km = rng.normal(0.3, 0.1, 40)
    knm = rng.normal(0.0, 0.1, 80)
    scores = np.concatenate([km, knm])
    labels = np.concatenate([np.ones(40), np.zeros(80)])
    clusters = ["b1|b1"] * 40 + [f"b{i % 5}|b{(i % 5) + 1}" for i in range(80)]
    return scores, labels, clusters


def test_diagnostics_shape():
    s, lab, _ = _synth()
    d = reference_diagnostics(s, lab)
    assert d["n_km"] == 40 and d["n_knm"] == 80
    assert 0.0 <= d["auc"] <= 1.0 and d["cllr"] >= 0.0


def test_write_round_trip(tmp_path):
    s, lab, c = _synth()
    out = tmp_path / "ref.npz"
    art = write_reference(
        out,
        scores=s,
        labels=lab,
        cluster_ids=c,
        name="t",
        generator="g",
        seed=1,
        datasets=[{"x": 1}],
        write=True,
    )
    assert out.exists() and out.with_suffix(".provenance.json").exists()
    data = np.load(out)
    assert "cluster_ids" in data.files
    assert data["cluster_ids"].shape[0] == len(s)
    # fixed-width unicode → stable tobytes() for the bootstrap cache key
    assert data["cluster_ids"].dtype.kind == "U"
    prov = json.loads(out.with_suffix(".provenance.json").read_text())
    assert prov["scorer_config_hash"] == DEFAULT_SCORER_CONFIG.config_hash
    assert prov["diagnostics"]["n_km"] == 40
    assert prov["n_sources"] >= 1
    assert prov["cluster_scheme"] == "pair-source-set"
    assert art.provenance == prov


def test_write_false_does_not_touch_disk(tmp_path):
    s, lab, c = _synth()
    out = tmp_path / "ref.npz"
    art = write_reference(
        out,
        scores=s,
        labels=lab,
        cluster_ids=c,
        name="t",
        generator="g",
        seed=None,
        datasets=[],
        write=False,
    )
    assert not out.exists()
    assert art.provenance["diagnostics"]["n_knm"] == 80
