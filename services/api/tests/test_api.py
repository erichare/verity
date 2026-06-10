"""API tests (FastAPI TestClient). The /compare data-path test runs only when the
Fadul scans are available locally."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from verity_api.main import app

client = TestClient(app)

_FADUL = Path.home() / ".cache" / "verity" / "cartridgeCaseScans" / "fadulMasked"


def test_health_lists_domains():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert {"impressed", "striated"} <= set(body["domains"])


def test_compare_rejects_unknown_domain():
    r = client.post(
        "/compare",
        data={"domain": "footwear"},
        files={
            "mark_a": ("a.x3p", b"x", "application/octet-stream"),
            "mark_b": ("b.x3p", b"y", "application/octet-stream"),
        },
    )
    assert r.status_code == 400


@pytest.mark.skipif(not _FADUL.exists(), reason="Fadul scans not cached locally")
def test_compare_impressed_known_match():
    with (_FADUL / "Fadul 1-1.x3p").open("rb") as fa, (_FADUL / "Fadul 1-2.x3p").open("rb") as fb:
        r = client.post(
            "/compare",
            data={"domain": "impressed"},
            files={
                "mark_a": ("Fadul 1-1.x3p", fa, "application/octet-stream"),
                "mark_b": ("Fadul 1-2.x3p", fb, "application/octet-stream"),
            },
        )
    assert r.status_code == 200
    rep = r.json()
    assert rep["domain"] == "impressed"
    assert "likelihood_ratio" in rep and "verbal" in rep and "scope_note" in rep
    assert rep["reference"]["name"].startswith("Fadul")
    # attribution overlay: previews + congruent regions for a known match
    assert "previews" in rep and "a" in rep["previews"] and "b" in rep["previews"]
    assert len(rep["attribution"]) > 0 and "x_frac" in rep["attribution"][0]


@pytest.mark.skipif(not _FADUL.exists(), reason="Fadul scans not cached locally")
def test_v1_compare_scorer_config_firewall():
    import json

    with (_FADUL / "Fadul 1-1.x3p").open("rb") as fa, (_FADUL / "Fadul 1-2.x3p").open("rb") as fb:
        files = {
            "mark_a": ("Fadul 1-1.x3p", fa.read(), "application/octet-stream"),
            "mark_b": ("Fadul 1-2.x3p", fb.read(), "application/octet-stream"),
        }
    # Off-config override → THE FIREWALL: scored, but the calibrated LR is refused.
    off = client.post(
        "/v1/compare",
        data={"domain": "impressed", "scorer_config": json.dumps({"cmr_corr": 0.9})},
        files=files,
    )
    assert off.status_code == 200
    body = off.json()
    assert body["calibrated"] is False
    assert "likelihood_ratio" not in body
    assert "score" in body  # the raw score under the requested config IS returned
    assert body["requested_scorer_config_hash"] != body["reference_scorer_config_hash"]

    # A config equal to the deployed default (by value) matches the reference → calibrated.
    on = client.post(
        "/v1/compare",
        data={"domain": "impressed", "scorer_config": json.dumps({"cmr_corr": 0.3})},
        files=files,
    )
    assert on.status_code == 200 and on.json().get("calibrated") is not False
    assert "likelihood_ratio" in on.json()


def test_cors_header_present_for_web_origin():
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


# --- toolmark domain ---------------------------------------------------------- #
def _toolmark_x3p(tmp_path: Path, name: str, shift: int = 0) -> Path:
    """A synthetic striated toolmark scan: anisotropic vertical striae with real
    (~0.5 µm) amplitude at 1.5 µm pitch — passes the modality + resolution scope."""
    import numpy as np
    import verity_x3p

    rng = np.random.default_rng(0)
    x = np.arange(256)
    stripes = 0.5e-6 * (
        np.sin(2 * np.pi * x / 12.0) + 0.4 * np.sin(2 * np.pi * x / 7.0 + 1.3)
    )
    z = np.tile(np.roll(stripes, shift), (256, 1)) + rng.normal(scale=0.03e-6, size=(256, 256))
    path = tmp_path / name
    verity_x3p.write_x3p(
        verity_x3p.Surface(data=z, increment_x=1.5e-6, increment_y=1.5e-6), str(path)
    )
    return path


def test_health_lists_toolmark_domain():
    r = client.get("/health")
    assert "toolmark" in r.json()["domains"]


def test_toolmark_reference_metadata_served():
    r = client.get("/v1/references/toolmark")
    assert r.status_code == 200
    body = r.json()
    assert body["name"].startswith("tmaRks")
    assert body["diagnostics"]["n_km"] > 1000  # the full tmaRks enumeration
    assert body["scorer_config_hash"]


def test_compare_toolmark_same_source(tmp_path):
    pa = _toolmark_x3p(tmp_path, "tm_a.x3p", shift=0)
    pb = _toolmark_x3p(tmp_path, "tm_b.x3p", shift=0)  # identical striae -> same source
    with pa.open("rb") as fa, pb.open("rb") as fb:
        r = client.post(
            "/compare",
            data={"domain": "toolmark"},
            files={
                "mark_a": ("tm_a.x3p", fa, "application/octet-stream"),
                "mark_b": ("tm_b.x3p", fb, "application/octet-stream"),
            },
        )
    assert r.status_code == 200, r.text
    rep = r.json()
    assert rep["domain"] == "toolmark"
    assert rep["score_kind"] == "cmr-1d"
    assert rep["reference"]["name"].startswith("tmaRks")
    assert rep["likelihood_ratio"] > 1  # identical marks -> same-source support
    # the score IS the congruent-striae count returned as attribution
    assert rep["score"] == float(len(rep["attribution"])) > 0
    assert "previews" in rep
