"""Tests for the glass-box artifact store + step endpoints.

Store behaviour is unit-tested directly; the step endpoints are exercised by injecting
synthetic surfaces into the store (so they need no cached scans), with the upload +
areal path gated on the Fadul cache.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from verity.surface import Surface
from verity_api.artifacts import STORE, ArtifactStore
from verity_api.decode import engine_version
from verity_api.main import app

client = TestClient(app)

_FADUL = Path.home() / ".cache" / "verity" / "cartridgeCaseScans" / "fadulMasked"


def _striated_surface(seed: int, nx: int = 256, ny: int = 256, dx: float = 1.5e-6) -> Surface:
    rng = np.random.default_rng(seed)
    x = np.arange(nx)
    stripes = 0.5e-6 * np.sin(2 * np.pi * x / 12.0 + seed * 0.1)
    z = np.tile(stripes, (ny, 1)) + rng.normal(scale=0.03e-6, size=(ny, nx))
    return Surface(heights=z, dx=dx, dy=dx)


def _store_surface(surface: Surface, store: ArtifactStore = STORE, **kw):
    return store.put_array(
        surface.heights,
        kind="surface",
        meta={"dx": surface.dx, "dy": surface.dy, "shape": list(surface.heights.shape)},
        produced_by={
            "step": "test",
            "code": "test",
            "inputs": [],
            "engine_version": engine_version(),
        },
        **kw,
    )


# --- store unit tests -------------------------------------------------------


def test_store_roundtrip():
    st = ArtifactStore()
    s = _striated_surface(0)
    art = _store_surface(s, st)
    assert art.handle.startswith("sha256:") and art.kind == "surface"
    got = st.surface(art.handle)
    assert got is not None and np.allclose(got.heights, s.heights) and got.dx == s.dx


def test_store_dedup_and_pitch_in_address():
    st = ArtifactStore()
    s = _striated_surface(0)
    assert _store_surface(s, st).handle == _store_surface(s, st).handle  # dedup
    other_pitch = Surface(heights=s.heights, dx=s.dx * 2, dy=s.dy)
    assert _store_surface(other_pitch, st).handle != _store_surface(s, st).handle  # pitch addressed


def test_store_ttl_eviction():
    st = ArtifactStore(ttl_s=10.0)
    a0 = _store_surface(_striated_surface(1), st, now=0.0)
    _store_surface(
        _striated_surface(2), st, now=100.0
    )  # a later put past the TTL evicts the stale one
    assert st.get(a0.handle) is None


def test_store_size_cap_lru():
    st = ArtifactStore(max_items=2)
    a = _store_surface(_striated_surface(1), st)
    _store_surface(_striated_surface(2), st)
    _store_surface(_striated_surface(3), st)  # evicts the least-recently-used (a)
    assert st.get(a.handle) is None


# --- step endpoints (synthetic surfaces injected, no scans needed) ----------


def test_signature_align_features_chain():
    a = [_store_surface(_striated_surface(i)).handle for i in range(4)]
    b = [_store_surface(_striated_surface(i)).handle for i in range(4)]  # same generators
    sig = client.post("/v1/steps/signature", data={"surface": a[0]}).json()
    assert sig["kind"] == "signature.1d" and sig["handle"].startswith("sha256:")
    assert "signature" in sig["preview"]  # trace_dict preview (same as include=trace)

    sa = [client.post("/v1/steps/signature", data={"surface": h}).json()["handle"] for h in a]
    sb = [client.post("/v1/steps/signature", data={"surface": h}).json()["handle"] for h in b]

    al = client.post("/v1/steps/align", data={"a": sa[0], "b": sb[0]})
    assert al.status_code == 200 and "lag" in al.json() and -1.0 <= al.json()["ccf"] <= 1.0

    ft = client.post("/v1/steps/features", data={"a": ",".join(sa), "b": ",".join(sb)})
    assert ft.status_code == 200
    feats = ft.json()["features"]
    assert "diag_contrast" in feats and len(feats["land_ccf_matrix"]) == 4


def test_preprocess_step_and_bad_cutoffs():
    h = _store_surface(_striated_surface(0)).handle
    body = client.post("/v1/steps/preprocess", data={"surface": h}).json()
    assert body["kind"] == "surface.bandpassed" and "grid" in body["preview"]
    bad = client.post(
        "/v1/steps/preprocess", data={"surface": h, "lambda_s": 1e-3, "lambda_c": 1e-6}
    )
    assert bad.status_code == 400  # require lambda_s < lambda_c


def test_artifact_404_and_wrong_kind():
    assert client.get("/v1/artifacts/sha256:deadbeef").status_code == 404
    h = _store_surface(_striated_surface(0)).handle  # a surface, not a signature
    assert client.post("/v1/steps/align", data={"a": h, "b": h}).status_code == 400


def test_get_artifact_metadata_data_preview():
    h = _store_surface(_striated_surface(0)).handle
    meta = client.get(f"/v1/artifacts/{h}")
    assert meta.status_code == 200 and meta.json()["kind"] == "surface"
    data = client.get(f"/v1/artifacts/{h}/data")
    assert data.status_code == 200 and data.headers["etag"] == h
    arr = np.load(io.BytesIO(data.content), allow_pickle=False)
    assert arr.shape == (256, 256)
    prev = client.get(f"/v1/artifacts/{h}/preview")
    assert prev.status_code == 200 and "grid" in prev.json()


def test_calibrate_emits_lr_against_reference():
    from verity.decision import DEFAULT_SCORER_CONFIG

    r = client.post(
        "/v1/steps/calibrate", data={"score": 5.0, "reference": "impressed", "ci": "false"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["calibrated"] is True
    assert body["likelihood_ratio"] > 0 and "log10_lr" in body
    assert body["reference"]["scorer_config_hash"]
    assert "calibration" in body and "tippett" in body["calibration"]
    # matching hash → config_verified true
    matched = client.post(
        "/v1/steps/calibrate",
        data={
            "score": 5.0,
            "reference": "impressed",
            "scorer_config_hash": DEFAULT_SCORER_CONFIG.config_hash,
            "ci": "false",
        },
    ).json()
    assert matched["config_verified"] is True


def test_calibrate_firewall_refuses_off_config():
    # THE FIREWALL: a declared config that doesn't match the reference's must NOT yield a
    # calibrated LR — raw score passed through, calibrated=false, with a structured reason.
    r = client.post(
        "/v1/steps/calibrate",
        data={"score": 5.0, "reference": "impressed", "scorer_config_hash": "deadbeef" * 8},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["calibrated"] is False
    assert "likelihood_ratio" not in body
    assert body["score"] == 5.0
    assert body["requested_scorer_config_hash"] == "deadbeef" * 8
    assert body["reference_scorer_config_hash"] and "scale" in body["reason"]


def test_calibrate_unknown_reference_404():
    assert (
        client.post("/v1/steps/calibrate", data={"score": 1.0, "reference": "nope"}).status_code
        == 404
    )


@pytest.mark.skipif(not _FADUL.exists(), reason="Fadul scans not cached locally")
def test_upload_then_areal_signature():
    with (_FADUL / "Fadul 1-1.x3p").open("rb") as f:
        up = client.post(
            "/v1/artifacts", files={"scan": ("a.x3p", f.read(), "application/octet-stream")}
        )
    assert up.status_code == 200
    body = up.json()
    assert body["kind"] == "surface" and body["meta"]["source_sha256"]
    areal = client.post("/v1/steps/areal-signature", data={"surface": body["handle"]})
    assert areal.status_code == 200 and areal.json()["kind"] == "signature.2d"
