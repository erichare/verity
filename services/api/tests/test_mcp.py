"""Remote MCP endpoint tests (mounted streamable-HTTP server at /mcp).

These drive the JSON-RPC endpoint with a TestClient (which runs the app lifespan,
so the MCP session manager is live) and assert the tools list and the metadata
tools answer. The file-path comparison is exercised by the stdio server's tests;
here we cover the wiring, the tool surface, and the base64 input guards.
"""

from __future__ import annotations

import base64
import json
import threading

import pytest
from fastapi.testclient import TestClient

from verity_api.main import app
from verity_api import mcp_server

# Streamable HTTP requires the client to accept both JSON and the SSE stream.
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _rpc(client: TestClient, method: str, params: dict | None = None, *, id: int = 1) -> dict:
    body = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        body["params"] = params
    r = client.post("/mcp", headers=_HEADERS, json=body)
    assert r.status_code == 200, r.text
    # json_response=True ⇒ a plain JSON body (no SSE framing to parse).
    return r.json()


def _call_tool(client: TestClient, name: str, arguments: dict):
    resp = _rpc(client, "tools/call", {"name": name, "arguments": arguments})
    assert "error" not in resp, resp.get("error")
    result = resp["result"]
    assert not result.get("isError"), result["content"]
    # Prefer the structured result; FastMCP wraps a non-dict return under a "result" key.
    sc = result.get("structuredContent")
    if sc is not None:
        return sc["result"] if set(sc) == {"result"} else sc
    return json.loads(result["content"][0]["text"])


@pytest.fixture(scope="module")
def client():
    # Context-manage so the lifespan (and thus the MCP session manager) runs. Module-scoped:
    # the session manager can only be run once per process, so share one client across tests.
    with TestClient(app) as c:
        # Initialize the MCP session (required handshake before tools/list|call).
        init = _rpc(
            c,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        )
        assert "result" in init, init
        c.post(
            "/mcp",
            headers=_HEADERS,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        yield c


def test_tools_list_exposes_the_six_tools(client):
    resp = _rpc(client, "tools/list")
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {
        "service_health",
        "detect_mark_type",
        "compare_marks",
        "calibrate_score",
        "list_references",
        "scorer_config",
    }


def test_service_health_tool(client):
    body = _call_tool(client, "service_health", {})
    assert body["status"] == "ok"
    assert {"impressed", "striated"} <= set(body["domains"])


def test_scorer_config_tool_has_hash(client):
    body = _call_tool(client, "scorer_config", {})
    assert "config_hash" in body and body["config_hash"]


def test_list_references_tool(client):
    refs = _call_tool(client, "list_references", {})
    assert isinstance(refs, list) and refs
    assert all("scorer_config_hash" in r for r in refs)


def test_calibrate_score_firewall_refuses_mismatched_hash(client):
    body = _call_tool(
        client,
        "calibrate_score",
        {"score": 0.1, "reference": "striated", "scorer_config_hash": "deadbeef"},
    )
    assert body["calibrated"] is False
    assert body["requested_scorer_config_hash"] == "deadbeef"


def test_compare_rejects_non_x3p_base64(client):
    resp = _rpc(
        client,
        "tools/call",
        {
            "name": "compare_marks",
            "arguments": {
                "domain": "impressed",
                "mark_a_base64": [base64.b64encode(b"not an x3p").decode()],
                "mark_b_base64": [base64.b64encode(b"also not").decode()],
            },
        },
    )
    # A bad scan surfaces as a tool error (isError), not a calibrated number.
    assert resp["result"]["isError"] is True
    assert "X3P" in resp["result"]["content"][0]["text"]


def test_compare_rejects_unknown_domain(client):
    resp = _rpc(
        client,
        "tools/call",
        {
            "name": "compare_marks",
            "arguments": {
                "domain": "footwear",
                "mark_a_base64": ["AA=="],
                "mark_b_base64": ["AA=="],
            },
        },
    )
    assert resp["result"]["isError"] is True
    assert "calibrated reference" in resp["result"]["content"][0]["text"]


@pytest.mark.parametrize("domain", ["impressed", "toolmark"])
def test_compare_rejects_extra_scans(client, domain):
    result = _rpc(
        client,
        "tools/call",
        {
            "name": "compare_marks",
            "arguments": {
                "domain": domain,
                "mark_a_base64": ["AA==", "AA=="],
                "mark_b_base64": ["AA=="],
            },
        },
    )["result"]
    assert result["isError"] is True
    assert "exactly one" in result["content"][0]["text"]


def test_summary_preserves_nested_scope_and_diagnostic_evidence():
    report = {
        "domain": "striated",
        "likelihood_ratio": 2.0,
        "evidence_note": {"level": "diagnostic_only", "reason": "not reportable evidence"},
        "scope": {
            "mark_a": [
                {
                    "admissible": True,
                    "checks": [
                        {"name": "signal", "passed": False, "reason": "low signal"},
                    ],
                }
            ]
        },
    }
    summary = mcp_server._summarize_compare(report)
    assert summary["evidence_note"] == report["evidence_note"]
    assert "not reportable evidence" in summary["summary"]
    assert any("low signal" in warning for warning in summary["scope_warnings"])


def test_decode_rejects_encoded_size_before_allocating(monkeypatch):
    from dataclasses import replace
    from verity_api import limits

    monkeypatch.setattr(limits, "LIMITS", replace(limits.LIMITS, max_file_bytes=3))

    def unexpected_decode(*args, **kwargs):
        pytest.fail("oversized base64 must be rejected before decoding")

    monkeypatch.setattr(base64, "b64decode", unexpected_decode)
    with pytest.raises(ValueError, match="per-file limit"):
        mcp_server._decode_scan("A" * 8, filename="scan.x3p", budget=limits.ByteBudget(100))


def test_compare_runs_in_bounded_pool_off_event_loop(client, monkeypatch):
    from verity_api import main

    thread_names = []

    def decode(*args, **kwargs):
        thread_names.append(threading.current_thread().name)
        return [object()], ["hash"], ["scan.x3p"]

    monkeypatch.setattr(mcp_server, "_decode_marks", decode)
    monkeypatch.setattr(main, "_compute_report", lambda *a, **kw: {"refused": True})
    result = _call_tool(
        client,
        "compare_marks",
        {
            "domain": "impressed",
            "mark_a_base64": ["AA=="],
            "mark_b_base64": ["AA=="],
        },
    )
    assert result["status"] == "refused"
    assert thread_names and all(name.startswith("verity-compare") for name in thread_names)


def test_compute_tools_use_shared_timeout(client, monkeypatch):
    from fastapi import HTTPException
    from verity_api import main

    async def timed_out(*args, **kwargs):
        raise HTTPException(status_code=503, detail="comparison timed out")

    monkeypatch.setattr(main, "_offload", timed_out)
    for name, arguments in [
        ("detect_mark_type", {"scan_base64": "AA=="}),
        (
            "compare_marks",
            {"domain": "impressed", "mark_a_base64": ["AA=="], "mark_b_base64": ["AA=="]},
        ),
        ("calibrate_score", {"score": 1.0, "reference": "impressed"}),
    ]:
        result = _rpc(client, "tools/call", {"name": name, "arguments": arguments})["result"]
        assert result["isError"] is True
        assert "comparison timed out" in result["content"][0]["text"]


def test_chunked_json_body_limit_is_413(client, monkeypatch):
    from dataclasses import replace
    from verity_api import limits

    monkeypatch.setattr(limits, "LIMITS", replace(limits.LIMITS, max_total_bytes=128))
    response = client.post(
        "/mcp",
        headers=_HEADERS,
        content=iter(
            [
                b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":',
                b" " * 256,
                b"{}}",
            ]
        ),
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "request body too large"
