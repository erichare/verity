"""Verity API access + agent-friendly formatting for the MCP server.

A thin ``requests`` client over the Verity REST API (default ``api.verity.codes``;
override with ``VERITY_API_URL``) plus formatters that turn the full comparison report
into a compact, honest result for an LLM: the likelihood ratio and its verbal weight, the
reference it is calibrated on, the reproducible content handle, and scope caveats — and,
when the engine refuses (an out-of-domain input, or an off-config score), the refusal
rather than a fabricated number. The session is injectable so the formatting and the HTTP
path can be tested without a live server.

This module imports no MCP machinery (only stdlib; ``requests`` lazily), so the
formatters are unit-testable on their own.
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_BASE_URL = "https://api.verity.codes"


class VerityAPIError(RuntimeError):
    """A non-2xx response from the Verity API."""


def _aslist(value: Any) -> list:
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _file_field(path: Any) -> tuple[str, Any]:
    if hasattr(path, "read"):
        return (getattr(path, "name", "scan.x3p"), path)
    return (os.path.basename(str(path)), open(str(path), "rb"))  # noqa: SIM115 - read by the request


class VerityAPI:
    """Thin client for the Verity REST API. ``session`` defaults to a ``requests`` session;
    inject a requests-compatible session (e.g. a FastAPI ``TestClient``) for testing."""

    def __init__(self, base_url: str | None = None, *, session: Any = None) -> None:
        self.base = (base_url or os.environ.get("VERITY_API_URL") or DEFAULT_BASE_URL).rstrip("/")
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    def _json(self, resp: Any) -> Any:
        if resp.status_code >= 400:
            raise VerityAPIError(f"{resp.status_code}: {resp.text[:400]}")
        return resp.json()

    def get(self, path: str, **kw: Any) -> Any:
        return self._json(self.session.get(self.base + path, **kw))

    def post(self, path: str, **kw: Any) -> Any:
        return self._json(self.session.post(self.base + path, **kw))

    def health(self) -> dict:
        return self.get("/health")

    def scorer_config(self) -> dict:
        return self.get("/v1/scorer-config")

    def references(self) -> list[dict]:
        return self.get("/v1/references")["references"]

    def detect(self, scan: Any) -> dict:
        return self.post("/detect", files={"scan": _file_field(scan)})

    def compare(
        self, domain: str, mark_a: Any, mark_b: Any, scorer_config: dict | None = None
    ) -> dict:
        import json

        files = [("mark_a", _file_field(p)) for p in _aslist(mark_a)]
        files += [("mark_b", _file_field(p)) for p in _aslist(mark_b)]
        data = {"domain": domain, "include": "calibration,recipe"}
        if scorer_config is not None:
            data["scorer_config"] = json.dumps(scorer_config)
        return self.post("/v1/compare", data=data, files=files)

    def calibrate(
        self, score: float, reference: str, scorer_config_hash: str | None = None
    ) -> dict:
        data: dict = {"score": score, "reference": reference, "ci": "true"}
        if scorer_config_hash:
            data["scorer_config_hash"] = scorer_config_hash
        return self.post("/v1/steps/calibrate", data=data)


# --- agent-friendly formatting (pure; no network) ---------------------------


def _human_lr(lr: float | None) -> str:
    if lr is None:
        return "—"
    return f"{lr:,.0f}x" if lr >= 1 else f"1/{1 / lr:,.0f}"


def _scope_warnings(report: dict) -> list[str]:
    """Surface any failed/warned applicability checks so the agent sees the caveats."""
    out: list[str] = []
    scope = report.get("scope") or {}
    for side in ("mark_a", "mark_b"):
        for chk in scope.get(side, []) or []:
            if not chk.get("passed", True):
                detail = chk.get("reason") or chk.get("severity") or "out of range"
                out.append(f"{side} · {chk.get('name')}: {detail}")
    return out


def summarize_compare(report: dict) -> dict:
    """Compact, honest summary of a comparison report for an LLM. Drops the bulky preview
    grids; preserves the LR, the reference, the reproducible handle, and scope caveats; and
    relays an engine refusal (out-of-domain) or an off-config result rather than inventing
    a calibrated number."""
    if report.get("refused"):
        return {
            "status": "refused",
            "domain": report.get("domain"),
            "reason": report.get("reason"),
            "scope_note": report.get("scope_note"),
            "summary": f"Refused — {report.get('reason')}",
        }
    if report.get("calibrated") is False:
        return {
            "status": "uncalibrated",
            "domain": report.get("domain"),
            "score": report.get("score"),
            "reason": report.get("uncalibrated_reason"),
            "requested_scorer_config_hash": report.get("requested_scorer_config_hash"),
            "reference_scorer_config_hash": report.get("reference_scorer_config_hash"),
            "summary": "Scored, but no calibrated LR returned: the scorer config does not "
            "match the reference's (the firewall). See `reason`.",
        }
    lr = report.get("likelihood_ratio")
    ref = report.get("reference") or {}
    handle = report.get("handle")
    ci_lo, ci_hi = report.get("log10_lr_ci_lo"), report.get("log10_lr_ci_hi")
    return {
        "status": "calibrated",
        "domain": report.get("domain"),
        "likelihood_ratio": lr,
        "log10_lr": report.get("log10_lr"),
        "log10_lr_ci": [ci_lo, ci_hi] if ci_lo is not None else None,
        "lr_bound_log10": report.get("lr_bound_log10"),
        "direction": report.get("direction"),
        "verbal": report.get("verbal"),
        "reference": {k: ref.get(k) for k in ("name", "n_km", "n_knm", "auc", "cllr", "cllr_min")},
        "attribution_regions": len(report.get("attribution") or []),
        "handle": handle,
        "scope_warnings": _scope_warnings(report),
        "scope_note": report.get("scope_note"),
        "summary": (
            f"{report.get('verbal')} (LR ~ {_human_lr(lr)}). Calibrated on "
            f"{ref.get('name')}. Reproducible recipe handle: {handle}."
        ),
    }
