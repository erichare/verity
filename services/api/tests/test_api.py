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
    assert "impressed" in body["domains"]


def test_compare_rejects_unknown_domain():
    r = client.post(
        "/compare",
        data={"domain": "footwear"},
        files={"mark_a": ("a.x3p", b"x", "application/octet-stream"),
               "mark_b": ("b.x3p", b"y", "application/octet-stream")},
    )
    assert r.status_code == 400


@pytest.mark.skipif(not _FADUL.exists(), reason="Fadul scans not cached locally")
def test_compare_impressed_known_match():
    with (_FADUL / "Fadul 1-1.x3p").open("rb") as fa, (_FADUL / "Fadul 1-2.x3p").open("rb") as fb:
        r = client.post(
            "/compare",
            data={"domain": "impressed"},
            files={"mark_a": ("Fadul 1-1.x3p", fa, "application/octet-stream"),
                   "mark_b": ("Fadul 1-2.x3p", fb, "application/octet-stream")},
        )
    assert r.status_code == 200
    rep = r.json()
    assert rep["domain"] == "impressed"
    assert "likelihood_ratio" in rep and "verbal" in rep and "scope_note" in rep
    assert rep["reference"]["name"].startswith("Fadul")
