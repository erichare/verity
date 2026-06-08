"""Tests for the /v1 router: inspectable intermediates + the scope endpoint."""

from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from verity.surface import Surface
from verity_api.intermediates import (
    calibration_diagnostics,
    parse_include,
    striated_bullet_intermediates,
)
from verity_api.main import app

client = TestClient(app)


def _striated_surface(seed: int, nx: int = 256, ny: int = 256, dx: float = 1.5e-6) -> Surface:
    rng = np.random.default_rng(seed)
    x = np.arange(nx)
    stripes = 0.5e-6 * np.sin(2 * np.pi * x / 12.0 + seed * 0.1)
    z = np.tile(stripes, (ny, 1)) + rng.normal(scale=0.03e-6, size=(ny, nx))
    return Surface(heights=z, dx=dx, dy=dx)


def _reference(seed: int = 0):
    rng = np.random.default_rng(seed)
    km = rng.normal(0.3, 0.1, 80)
    knm = rng.normal(0.0, 0.1, 320)
    return np.concatenate([km, knm]), np.concatenate([np.ones(80), np.zeros(320)]), "synthetic ref"


def test_parse_include():
    assert parse_include(None) == set()
    assert parse_include("calibration, features") == {"calibration", "features"}
    assert parse_include("all") == {"calibration", "features", "perland", "trace"}
    assert parse_include("bogus") == set()


def test_calibration_diagnostics_shape():
    scores, labels, name = _reference()
    diag = calibration_diagnostics(scores, labels, 0.3, name)
    assert diag["n_km"] == 80 and diag["n_knm"] == 320
    assert "tippett" in diag and "km_knm_hist" in diag
    assert len(diag["tippett"]["log10_lr"]) == len(diag["tippett"]["km_ge"])
    assert np.isfinite(diag["this_log10_lr"])


def test_striated_bullet_intermediates_features_and_trace():
    a = [_striated_surface(i) for i in range(4)]
    b = [_striated_surface(i) for i in range(4)]  # same source (identical generators)
    ref = _reference()
    out = striated_bullet_intermediates(
        a, b, {"features", "trace", "perland"}, single_land_reference=ref
    )
    assert "features" in out
    feats = out["features"]
    assert "diag_contrast" in feats and "land_ccf_matrix" in feats
    assert len(feats["land_ccf_matrix"]) == 4  # 4x4 land matrix
    assert "trace" in out and "signature" in out["trace"]["a"]
    assert "per_land" in out and len(out["per_land"]["lands"]) == 4


def test_v1_scope_endpoint_rejects_unknown_domain():
    r = client.post(
        "/v1/scope",
        data={"domain": "footwear", "mode": "warn"},
        files={"scan": ("a.x3p", b"x", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_v1_scope_rejects_invalid_mode():
    r = client.post(
        "/v1/scope",
        data={"domain": "striated", "mode": "bogus"},
        files={"scan": ("a.x3p", b"x", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_v1_compare_rejects_unknown_domain():
    r = client.post(
        "/v1/compare",
        data={"domain": "footwear", "include": "all"},
        files={
            "mark_a": ("a.x3p", b"x", "application/octet-stream"),
            "mark_b": ("b.x3p", b"y", "application/octet-stream"),
        },
    )
    assert r.status_code == 400


def test_unversioned_compare_still_present():
    # the live web depends on the unversioned route — it must keep existing
    paths = {r.path for r in app.routes}
    assert "/compare" in paths and "/v1/compare" in paths and "/v1/scope" in paths
