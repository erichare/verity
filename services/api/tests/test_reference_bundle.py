"""Reference bundle loader: backward-compat, provenance, cluster IDs, drift guard."""

from __future__ import annotations

import json

import numpy as np

from verity_api.reference_bundle import load_bundle
from verity_api.references import load_reference_bundle


def test_legacy_npz_loads_without_clusters(tmp_path):
    p = tmp_path / "legacy.npz"
    np.savez(p, scores=np.array([0.1, 0.2, 0.3]), labels=np.array([1.0, 0.0, 0.0]))
    b = load_bundle(p, name="legacy")
    assert b.cluster_ids is None
    assert b.provenance == {}
    assert b.scorer_config_hash is None


def test_bundle_with_clusters_and_sidecar(tmp_path):
    p = tmp_path / "r.npz"
    np.savez(
        p,
        scores=np.array([0.1, 0.2]),
        labels=np.array([1.0, 0.0]),
        cluster_ids=np.array(["a|a", "a|b"]),
    )
    p.with_suffix(".provenance.json").write_text(
        json.dumps({"scorer_config_hash": "abc", "n_sources": 2})
    )
    b = load_bundle(p, name="r")
    assert list(b.cluster_ids) == ["a|a", "a|b"]
    assert b.scorer_config_hash == "abc"
    assert b.provenance["n_sources"] == 2


def test_shipped_bullet_reference_carries_clusters_and_provenance():
    b = load_reference_bundle("striated")  # bullet_pooled
    assert b.cluster_ids is not None
    assert len(b.cluster_ids) == len(b.scores)
    assert b.scorer_config_hash  # provenance sidecar present
    assert b.provenance["diagnostics"]["n_km"] == 146
