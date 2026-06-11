"""Tests for the /v1 router: inspectable intermediates + the scope endpoint."""

from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from verity.decision import DEFAULT_SCORER_CONFIG
from verity.surface import Surface
from verity_api.intermediates import (
    calibration_diagnostics,
    parse_include,
    striated_bullet_intermediates,
)
from verity_api.main import app
from verity_api.recipe import build_recipe

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
    assert parse_include("all") == {"calibration", "features", "perland", "trace", "recipe"}
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


# --- glass-box: scorer config, references, and the reproducible recipe -------


def _recipe_resp(lr: float = 146.0) -> dict:
    return {
        "domain": "impressed",
        "score": 5.0,
        "score_kind": "cmr-2d",
        "likelihood_ratio": lr,
        "log10_lr": float(np.log10(lr)),
        "log10_lr_ci_lo": 1.0,
        "log10_lr_ci_hi": 2.0,
        "lr_ci_method": "bootstrap-clustered",
        "lr_bound_log10": 2.0,
        "lr_bound_hit": True,
        "direction": "same source",
        "verbal": "moderately strong support for same source",
        "reference": {"name": "synthetic ref"},
        "provenance": {
            "engine_version": "0.1.0",
            "api_version": "0.1.0",
            "input_hashes": {"mark_a": ["aa"], "mark_b": ["bb"]},
        },
    }


def test_build_recipe_structure_and_deterministic_handle():
    rp = {"scorer_config_hash": "refhash", "datasets": [{"tag": "x"}], "diagnostics": {"auc": 0.99}}
    r = build_recipe(_recipe_resp(), domain="impressed", reference_provenance=rp)
    assert r["handle"].startswith("sha256:")
    assert r["scorer_config_hash"] == DEFAULT_SCORER_CONFIG.config_hash
    assert r["reference"]["scorer_config_hash"] == "refhash"
    assert r["result"]["lr_bound_hit"] is True  # bound-limited flag rides into the recipe
    steps = [s["step"] for s in r["steps"]]
    assert steps[:2] == ["decode", "preprocess"]
    assert {"calibrate", "uncertainty"} <= set(steps)
    # decode step carries the input hashes (the provenance spine)
    decode = next(s for s in r["steps"] if s["step"] == "decode")
    assert decode["inputs"] == {"mark_a": ["aa"], "mark_b": ["bb"]}
    # deterministic: same computation → same handle; changed result → different handle
    assert (
        build_recipe(_recipe_resp(), domain="impressed", reference_provenance=rp)["handle"]
        == r["handle"]
    )
    assert (
        build_recipe(_recipe_resp(lr=999.0), domain="impressed", reference_provenance=rp)["handle"]
        != r["handle"]
    )


def test_v1_scorer_config_endpoint():
    r = client.get("/v1/scorer-config")
    assert r.status_code == 200
    body = r.json()
    assert body["config_hash"] == DEFAULT_SCORER_CONFIG.config_hash
    assert body["lambda_s"] == DEFAULT_SCORER_CONFIG.lambda_s
    assert body["name"] == DEFAULT_SCORER_CONFIG.name


def test_v1_references_list_carries_provenance():
    r = client.get("/v1/references")
    assert r.status_code == 200
    refs = r.json()["references"]
    ids = {x["id"] for x in refs}
    assert {"striated", "impressed", "striated_single"} <= ids
    impressed = next(x for x in refs if x["id"] == "impressed")
    assert impressed["scorer_config_hash"]  # what the LR is calibrated under
    assert impressed["diagnostics"]["n_km"] >= 1
    assert impressed["datasets"]  # source provenance


def test_v1_reference_by_id_and_404():
    assert client.get("/v1/references/impressed").status_code == 200
    assert client.get("/v1/references/striated_single").status_code == 200
    assert client.get("/v1/references/nope").status_code == 404


def test_v1_compare_invalid_scorer_config_400():
    # The scorer-config override is parsed before any scoring, so bad input is a clean 400
    # (dummy files are never read).
    files = {
        "mark_a": ("a.x3p", b"x", "application/octet-stream"),
        "mark_b": ("b.x3p", b"y", "application/octet-stream"),
    }
    for bad in ("{not json", '{"bogus": 1}', '{"lambda_s": 1e-3, "lambda_c": 1e-6}'):
        r = client.post(
            "/v1/compare", data={"domain": "striated", "scorer_config": bad}, files=files
        )
        assert r.status_code == 400, bad
