"""The Python SDK (clients/python/verity_client.py) exercised against the in-process API.

The client is transport-agnostic: we inject a FastAPI ``TestClient`` as its session and
point it at base_url="" so it drives the real app with no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from verity_api.main import app

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "clients" / "python"))

from verity_client import VerityClient  # noqa: E402

_FADUL = Path.home() / ".cache" / "verity" / "cartridgeCaseScans" / "fadulMasked"


def _client() -> VerityClient:
    return VerityClient(base_url="", session=TestClient(app))


def test_client_meta():
    c = _client()
    assert c.health()["status"] == "ok"
    assert c.scorer_config()["config_hash"]
    ids = {r["id"] for r in c.references()}
    assert {"striated", "impressed", "striated_single"} <= ids
    assert c.reference("impressed")["diagnostics"]["n_km"] >= 1


def test_client_calibrate_and_firewall():
    c = _client()
    ok = c.calibrate(5.0, "impressed", ci=False)
    assert ok["calibrated"] and ok["likelihood_ratio"] > 0
    refused = c.calibrate(5.0, "impressed", scorer_config_hash="deadbeef" * 8, ci=False)
    assert refused["calibrated"] is False


@pytest.mark.skipif(not _FADUL.exists(), reason="Fadul scans not cached locally")
def test_client_compare_and_reproduce():
    c = _client()
    a, b = _FADUL / "Fadul 1-1.x3p", _FADUL / "Fadul 1-2.x3p"
    r = c.compare("impressed", a, b)
    assert "likelihood_ratio" in r and r["handle"].startswith("sha256:")
    assert r["recipe"]["steps"]  # the methods-as-JSON came back
    # reproducibility is a hash-equality check
    assert c.reproduce("impressed", a, b, expect_handle=r["handle"])


@pytest.mark.skipif(not _FADUL.exists(), reason="Fadul scans not cached locally")
def test_client_step_graph():
    c = _client()
    h = c.upload(_FADUL / "Fadul 1-1.x3p")
    assert c.artifact(h)["kind"] == "surface"
    areal = c.step("areal-signature", surface=h)
    assert areal["kind"] == "signature.2d" and areal["produced_by"]["inputs"] == [h]
