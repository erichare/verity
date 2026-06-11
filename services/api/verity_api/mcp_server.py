"""Remote MCP server — Verity's calibrated comparison over streamable HTTP.

The stdio server in ``services/mcp`` runs on the agent's own machine, so it reads
local ``.x3p`` file paths and uploads them. This server is hosted *inside the API*
(mounted at ``/mcp``), so it cannot see the agent's filesystem: scans are passed
**inline** as base64-encoded ``.x3p`` bytes. Everything else is identical — each
tool reuses the same in-process engine the REST routes use, so the calibration
firewall, the scope guard, and the reproducible recipe handles all carry over. An
agent gets a calibrated weight of evidence on a named reference, or an honest
refusal — never a fabricated number.

Transport: **stateless** streamable HTTP with JSON responses. Each call is
independent (no per-connection session state), so the endpoint is plain
request/response and survives a buffering reverse proxy (Railway) unchanged.

This module's only top-level imports are cycle-free (engine + the API's decode /
references / limits helpers); the heavier comparison orchestration in ``main`` is
imported lazily inside the tool body, so importing this module never triggers a
circular import with ``main`` (which mounts it).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from verity.decision import DEFAULT_SCORER_CONFIG
from verity.detect import detect_domain

from . import limits
from .decode import engine_version, surface_from_bytes
from .references import all_reference_metadata, available_domains


def _transport_security() -> TransportSecuritySettings:
    """DNS-rebinding (Host/Origin) protection for the endpoint. The hosted API sits behind
    a reverse proxy and is reached over several hostnames (the custom domain, the platform
    domain, health checks), so protection is **off by default** — set
    ``VERITY_MCP_ALLOWED_HOSTS`` (comma-separated; ``VERITY_MCP_ALLOWED_ORIGINS`` too, for
    browser clients) to lock it down to known hosts."""
    hosts = [h.strip() for h in os.environ.get("VERITY_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    if not hosts:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    origins = [
        o.strip() for o in os.environ.get("VERITY_MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()
    ]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True, allowed_hosts=hosts, allowed_origins=origins
    )


mcp = FastMCP(
    "verity",
    stateless_http=True,
    json_response=True,
    # Serve the JSON-RPC endpoint at exactly /mcp (no trailing-slash redirect): the route
    # is registered directly on the API app in ``main``, not mounted under a prefix, so a
    # client POSTing to https://<host>/mcp gets a 200, not a 307 some connectors won't follow.
    streamable_http_path="/mcp",
    transport_security=_transport_security(),
)


# --- input decoding ---------------------------------------------------------


def _decode_scan(b64: str, *, filename: str, budget: limits.ByteBudget) -> tuple[bytes, str]:
    """Decode one base64 ``.x3p`` payload, enforcing the same per-file / total-size and
    zip-bomb guards as an HTTP upload, and return ``(bytes, sha256)`` — the content hash
    is the provenance spine that ties a report back to the exact scanned file."""
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{filename}: not valid base64 ({exc})") from exc
    if len(data) > limits.LIMITS.max_file_bytes:
        raise ValueError(f"{filename} exceeds the {limits.LIMITS.max_file_bytes}-byte per-file limit")
    budget.take(len(data))
    try:
        limits.validate_x3p(data, filename=filename)
    except limits.UploadRejected as exc:
        raise ValueError(exc.detail) from exc
    return data, hashlib.sha256(data).hexdigest()


def _decode_marks(b64s: list[str], *, side: str, budget: limits.ByteBudget):
    surfaces, hashes, names = [], [], []
    for i, b64 in enumerate(b64s):
        name = f"{side}_{i}.x3p"
        data, digest = _decode_scan(b64, filename=name, budget=budget)
        surfaces.append(surface_from_bytes(data))
        hashes.append(digest)
        names.append(name)
    return surfaces, hashes, names


# --- agent-friendly comparison formatting (parity with services/mcp) --------
# A pure summary of the full comparison report for an LLM: the LR and its verbal
# weight, the reference it is calibrated on, the reproducible handle, and scope
# caveats — and, when the engine refuses (out of domain) or declines to calibrate
# (off-config score), that status rather than a fabricated number. Kept in sync
# with ``verity_mcp.api.summarize_compare`` (the stdio server's formatter).


def _human_lr(lr: float | None) -> str:
    if lr is None:
        return "—"
    return f"{lr:,.0f}x" if lr >= 1 else f"1/{1 / lr:,.0f}"


def _scope_warnings(report: dict) -> list[str]:
    out: list[str] = []
    scope = report.get("scope") or {}
    for side in ("mark_a", "mark_b"):
        for chk in scope.get(side, []) or []:
            if not chk.get("passed", True):
                detail = chk.get("reason") or chk.get("severity") or "out of range"
                out.append(f"{side} · {chk.get('name')}: {detail}")
    return out


def _summarize_compare(report: dict) -> dict:
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


# --- tools ------------------------------------------------------------------


@mcp.tool()
def service_health() -> dict:
    """Verity service status and the mark types (domains) it can calibrate."""
    return {"status": "ok", "engine_version": engine_version(), "domains": available_domains()}


@mcp.tool()
def detect_mark_type(scan_base64: str) -> dict:
    """Suggest whether a 3-D surface scan is a STRIATED mark (bullet land, toolmark) or an
    IMPRESSED mark (cartridge breech face), from striation anisotropy. `scan_base64` is the
    raw bytes of one `.x3p` file, base64-encoded. The mark type selects the calibration
    reference, so confirm it before comparing."""
    budget = limits.ByteBudget(limits.LIMITS.max_total_bytes)
    data, _ = _decode_scan(scan_base64, filename="scan.x3p", budget=budget)
    try:
        domain, coherence = detect_domain(surface_from_bytes(data))
    except Exception as exc:  # noqa: BLE001 - surface a clean tool error, not a 500
        raise ValueError(f"could not read X3P: {exc}") from exc
    return {"domain": domain, "coherence": round(coherence, 3)}


@mcp.tool()
def compare_marks(
    domain: str,
    mark_a_base64: list[str],
    mark_b_base64: list[str],
    scorer_config: dict | None = None,
) -> dict:
    """Compare two forensic marks into a CALIBRATED likelihood ratio with a reproducible
    recipe handle and region-level attribution.

    - `domain`: "striated" (bullet lands / toolmarks) or "impressed" (cartridge breech faces).
    - `mark_a_base64`, `mark_b_base64`: base64-encoded `.x3p` bytes — one per side for
      impressed; for a bullet, pass ALL of that bullet's land scans (aggregating the lands is
      the strong path). (This server is hosted, so it cannot read local paths — send the bytes.)
    - `scorer_config`: optional hyperparameter override (e.g. {"lambda_c": 8e-6}); if it
      doesn't match the reference's config, the result is the raw score with NO calibrated
      LR (the firewall).

    Returns the likelihood ratio + ENFSI verbal weight, the named reference it is calibrated
    on, the content handle (the same inputs reproduce it), and any scope caveats — or an
    honest refusal if an input is outside the validated domain. This is a calibrated weight
    of evidence on a named reference, not a claim about the error rate of examination."""
    # Lazy: the comparison orchestration lives in ``main`` (which mounts this server);
    # importing it here, at call time, keeps module import cycle-free.
    from .main import _compute_report, _coerce_scorer_config

    if domain not in available_domains():
        raise ValueError(
            f"domain {domain!r} has no calibrated reference; available: {available_domains()}"
        )
    if not mark_a_base64 or not mark_b_base64:
        raise ValueError("provide at least one scan per mark")
    if len(mark_a_base64) + len(mark_b_base64) > limits.LIMITS.max_files:
        raise ValueError(
            f"{len(mark_a_base64) + len(mark_b_base64)} files exceeds the "
            f"{limits.LIMITS.max_files}-file limit"
        )

    budget = limits.ByteBudget(limits.LIMITS.max_total_bytes)
    surfaces_a, hashes_a, names_a = _decode_marks(mark_a_base64, side="mark_a", budget=budget)
    surfaces_b, hashes_b, names_b = _decode_marks(mark_b_base64, side="mark_b", budget=budget)
    config = _coerce_scorer_config(scorer_config)
    provenance = {
        "api_version": "0.1.0",
        "engine_version": engine_version(),
        "mark_a": names_a,
        "mark_b": names_b,
        "input_hashes": {"mark_a": hashes_a, "mark_b": hashes_b},
        "transport": "mcp",
    }
    report = _compute_report(
        domain,
        surfaces_a,
        surfaces_b,
        provenance=provenance,
        include={"calibration", "recipe"},
        config=config,
    )
    return _summarize_compare(report)


@mcp.tool()
def list_references() -> list[dict]:
    """The calibration reference populations and their provenance — the scorer-config hash
    each was built under, its source datasets, and its discrimination/calibration
    diagnostics (AUC, Cllr). This is exactly what every likelihood ratio is calibrated on."""
    return all_reference_metadata()


@mcp.tool()
def scorer_config() -> dict:
    """The deployed scorer hyperparameters and their content hash. A calibrated LR is valid
    only against a reference built under this same config hash (the firewall)."""
    return {**DEFAULT_SCORER_CONFIG.to_dict(), "config_hash": DEFAULT_SCORER_CONFIG.config_hash}


@mcp.tool()
def calibrate_score(score: float, reference: str, scorer_config_hash: str | None = None) -> dict:
    """Map a comparison score to a bounded likelihood ratio against a named reference
    ("striated" | "impressed" | "striated_single"), with its calibration curve and credible
    interval. If `scorer_config_hash` is given and doesn't match the reference's,
    calibration is refused (the firewall)."""
    from .steps import step_calibrate

    try:
        return step_calibrate(
            score=score, reference=reference, scorer_config_hash=scorer_config_hash, ci=True
        )
    except Exception as exc:  # noqa: BLE001 - HTTPException(404) → a clean tool error
        detail: Any = getattr(exc, "detail", None) or str(exc)
        raise ValueError(detail) from exc
