"""Security-hardening tests: the per-IP rate limit reaches the hosted MCP endpoint, and
every response carries the baseline security headers."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from verity_api import limits as limits_mod
from verity_api import main as main_mod
from verity_api.main import app

client = TestClient(app)

_SECURITY_HEADERS = (
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "content-security-policy",
)


def test_security_headers_present_on_health():
    r = client.get("/health")
    assert r.status_code == 200
    for h in _SECURITY_HEADERS:
        assert h in r.headers, f"missing security header: {h}"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_security_headers_present_on_error_responses():
    # The headers middleware wraps the limiter, so even an early rejection carries them.
    r = client.post("/compare", data={"domain": "footwear"}, files={})
    assert r.status_code in (400, 422)
    assert r.headers.get("x-content-type-options") == "nosniff"


@pytest.fixture
def exhausted_budget(monkeypatch):
    """Force a 0-request budget so the limiter refuses a metered path at the middleware,
    before the route handler runs (avoids standing up the MCP session manager here)."""
    monkeypatch.setattr(
        limits_mod, "LIMITS", replace(limits_mod.LIMITS, rate_limit=0, rate_window_s=60.0)
    )
    main_mod._rate_hits.clear()
    yield
    main_mod._rate_hits.clear()


def test_mcp_endpoint_is_metered(exhausted_budget):
    # Pre-change /mcp was unmetered and would route through to the JSON-RPC handler (not 429).
    # Now it is in the metered set, so an exhausted budget refuses it at the middleware.
    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers={"Accept": "application/json, text/event-stream"},
    )
    assert r.status_code == 429
    assert r.json()["detail"].startswith("rate limit")


def test_cheap_gets_are_not_metered(exhausted_budget):
    # Unmetered read endpoints stay open even with the upload budget exhausted.
    assert client.get("/health").status_code == 200


def _request_with(headers: dict[str, str], client_host: str = "10.0.0.1"):
    from fastapi import Request

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/compare",
            "query_string": b"",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (client_host, 12345),
        }
    )


def test_client_ip_ignores_forged_forwarded_entries(monkeypatch):
    """With trusted proxy headers on, only the RIGHTMOST X-Forwarded-For entry
    counts — it is the hop appended by the edge proxy. The leftmost entries are
    client-supplied, so honoring them would let one client forge fresh
    rate-limit identities per request."""
    monkeypatch.setattr(main_mod, "_TRUST_PROXY_HEADERS", True)
    forged = _request_with({"x-forwarded-for": "6.6.6.6, 7.7.7.7, 203.0.113.9"})
    assert main_mod._client_ip(forged) == "203.0.113.9"

    single = _request_with({"x-forwarded-for": "203.0.113.9"})
    assert main_mod._client_ip(single) == "203.0.113.9"

    # A degenerate all-empty header falls back to the socket peer.
    empty = _request_with({"x-forwarded-for": " , "})
    assert main_mod._client_ip(empty) == "10.0.0.1"

    monkeypatch.setattr(main_mod, "_TRUST_PROXY_HEADERS", False)
    untrusted = _request_with({"x-forwarded-for": "6.6.6.6"})
    assert main_mod._client_ip(untrusted) == "10.0.0.1"
