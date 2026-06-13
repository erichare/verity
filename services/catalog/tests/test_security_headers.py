"""The catalog API attaches baseline security headers to every response.

Hits the DB-free ``/healthz`` so it runs even on a fresh clone / CI (no populated
catalog required)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from verity_catalog.api.app import app  # noqa: E402

client = TestClient(app)

_SECURITY_HEADERS = (
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "content-security-policy",
)


def test_security_headers_present_on_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    for h in _SECURITY_HEADERS:
        assert h in r.headers, f"missing security header: {h}"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
