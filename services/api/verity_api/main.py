"""Verity comparison API — serves the calibrated :class:`ComparisonReport`.

``POST /compare`` takes two X3P uploads + a domain, decodes them with the native
``verity_x3p`` codec, runs the domain scorer, calibrates against the bundled
reference, and returns the report JSON. ``GET /health`` lists the calibrated
domains. The decision stays in the engine's bounded-LR firewall; this layer only
decodes, dispatches, and serializes. The Next.js UI renders the response.

A versioned ``/v1`` router exposes the same comparison plus, on request
(``include=calibration,features,perland,trace``), the algorithm's **intermediate
computations** — the reference calibration curve with this score on it, the
CCF-matrix structure features, per-land evidence, and the pipeline trace — so the
result is inspectable end to end. ``/v1/scope`` runs the applicability-domain
guard on a single scan. The unversioned routes are preserved as thin aliases.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import os
import tempfile
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import verity_x3p
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel

from verity import land_trace
from verity.compare import compare_bullets_with_previews, compare_with_previews
from verity.decision import (
    DEFAULT_SCORER_CONFIG,
    ScopeReport,
    ScorerConfig,
    cached_bootstrap_calibration,
    check_applicability,
    default_n_boot,
)
from verity.detect import detect_domain
from verity.surface import Surface

from . import limits
from .intermediates import (
    calibration_diagnostics,
    parse_include,
    striated_bullet_intermediates,
    trace_dict,
)
from .mcp_server import mcp as mcp_server
from .recipe import build_recipe
from .references import (
    all_reference_metadata,
    available_domains,
    load_reference_bundle,
    load_striated_single_bundle,
    load_striated_single_land,
    reference_metadata,
)
from .steps import steps as steps_router

_LAMBDA_S, _LAMBDA_C = DEFAULT_SCORER_CONFIG.lambda_s, DEFAULT_SCORER_CONFIG.lambda_c


def _engine_version() -> str:
    try:
        return version("verity")
    except PackageNotFoundError:
        return "unknown"


_DESCRIPTION = """\
**Verity** — calibrated, bounded **likelihood ratios** for forensic surface
comparison, across **striated** marks (bullet lands, toolmarks) and **impressed**
marks (cartridge breech faces).

Upload X3P 3-D topography scans; the engine decodes them with the native
`verity_x3p` codec, scores the comparison, calibrates the score to a likelihood
ratio against a named reference population (with a characterized cost, *Cllr*, and
a bootstrap credible interval), and returns region-level **attribution** — the
parts of the marks that drove the match.

The decision stays behind a glass-box statistical firewall: the reported LR is a
monotone, bounded transform of the score, interpretable regardless of how the score
was computed. It is *not* a claim about the error rate of forensic examination,
which remains unknown.

The versioned **`/v1`** routes expose the algorithm's intermediate steps on request
(`include=calibration,features,perland,trace,recipe`), a reproducible **recipe** —
the methods section as JSON, with a content **handle** — an applicability-domain guard
(`/v1/scope`), and metadata on the deployed scorer config (`/v1/scorer-config`) and the
calibration references (`/v1/references`).

Every pipeline stage is also **independently addressable** as a content-hashed artifact
graph: `POST /v1/artifacts` a scan for a surface handle, then chain
`/v1/steps/{preprocess,signature,areal-signature,align,features}` by handle — each
intermediate fetchable at `/v1/artifacts/{handle}` — and `/v1/steps/calibrate` maps a
score to a bounded LR behind the calibration firewall (it refuses to calibrate a score
whose scorer-config hash doesn't match the reference's).

For AI agents, the same calibrated tools are served over **MCP** (Model Context Protocol)
at **`/mcp`** — streamable HTTP, stateless — exposing `compare_marks`, `detect_mark_type`,
`calibrate_score`, `list_references`, `scorer_config`, and `service_health`. Scans are
passed inline as base64-encoded X3P (a hosted server can't read the agent's local files).

Web app: <https://verity.codes> · Method & references: <https://verity.codes/#science>
"""

_TAGS = [
    {"name": "compare", "description": "Compare two marks → a calibrated likelihood-ratio report."},
    {"name": "meta", "description": "Service health and mark-type detection."},
    {"name": "v1", "description": "Versioned API: comparison with inspectable intermediates."},
]


def _warm_caches() -> None:
    """Pre-build each bundled reference's bootstrap calibration ensemble so the
    first comparison doesn't pay the credible-interval cost on the request path.
    ``n_boot`` resolves ``VERITY_LR_BOOTSTRAP_N`` — the same knob the request path
    uses, so the warmed key is the key requests hit. With ``VERITY_ENSEMBLE_CACHE_DIR``
    set, the warmed ensembles also persist, so the *next* process restores instead
    of refitting."""
    try:
        bundles = [load_reference_bundle(d) for d in available_domains()]
        bundles.append(load_striated_single_bundle())
        for b in bundles:
            cached_bootstrap_calibration(
                b.scores, b.labels, n_boot=default_n_boot(), seed=0, cluster_ids=b.cluster_ids
            )
    except Exception:  # noqa: BLE001 - warmup is best-effort; never block startup
        pass


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Warm the bootstrap-CI caches off the request path AND off startup: run in a
    # daemon thread so the server is ready immediately (the first comparison during
    # warmup simply computes its ensemble on demand).
    import threading

    threading.Thread(target=_warm_caches, daemon=True).start()
    # The mounted /mcp app does not get its lifespan run by Starlette, so drive the
    # MCP session manager from here — required even when stateless.
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(
    title="Verity comparison API",
    version="0.1.0",
    summary="Calibrated, bounded likelihood ratios for forensic surface comparison.",
    description=_DESCRIPTION,
    contact={"name": "Verity", "url": "https://verity.codes"},
    license_info={"name": "MIT / Apache-2.0"},
    openapi_tags=_TAGS,
    lifespan=_lifespan,
)


class HealthResponse(BaseModel):
    status: str
    engine_version: str
    domains: list[str]


class DetectResponse(BaseModel):
    domain: str
    coherence: float


# The Next.js UI is a separate origin, so the browser needs CORS. Defaults cover
# local dev (localhost / 127.0.0.1 :3000); override with VERITY_CORS_ORIGINS
# (comma-separated) for a deployed front end.
_cors_origins = [
    o.strip()
    for o in os.environ.get(
        "VERITY_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Per-IP sliding-window rate limit on the upload endpoints. In-process (fine for a
# single instance); front a shared store (Redis) when scaling horizontally.
_RATE_LIMITED_PATHS = frozenset(
    {
        "/compare",
        "/v1/compare",
        "/v1/compare/report.pdf",
        "/detect",
        "/v1/scope",
        # glass-box step API: the upload + the compute steps (cheap GETs are unmetered).
        "/v1/artifacts",
        "/v1/steps/preprocess",
        "/v1/steps/signature",
        "/v1/steps/areal-signature",
        "/v1/steps/align",
        "/v1/steps/features",
        "/v1/steps/calibrate",
        # The hosted MCP endpoint orchestrates the same CPU-bound compare; meter it too
        # so an agent client can't bypass the per-IP cap that the HTTP routes carry.
        "/mcp",
    }
)
_MAX_TRACKED_IPS = 10_000
_rate_hits: dict[str, deque] = {}
# Behind a reverse proxy (Railway, etc.) request.client.host is the proxy, so the rate
# limit would be one global bucket. Set VERITY_TRUST_PROXY_HEADERS=1 in such a deploy to
# key on the real client from X-Forwarded-For. Leave off for direct/local exposure
# (where the header would be client-spoofable).
_TRUST_PROXY_HEADERS = os.environ.get("VERITY_TRUST_PROXY_HEADERS", "").strip().lower() in (
    "1",
    "true",
    "yes",
)


def _client_ip(request: Request) -> str:
    if _TRUST_PROXY_HEADERS:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "anonymous"


def _prune_rate_hits(now: float, window: float) -> None:
    stale = [ip for ip, h in _rate_hits.items() if not h or now - h[-1] > window]
    for ip in stale:
        del _rate_hits[ip]


def _rate_ok(request: Request) -> bool:
    lim = limits.LIMITS
    ip = _client_ip(request)
    now = time.monotonic()
    hits = _rate_hits.get(ip)
    if hits is None:
        if len(_rate_hits) > _MAX_TRACKED_IPS:
            _prune_rate_hits(now, lim.rate_window_s)
        hits = _rate_hits[ip] = deque()
    while hits and now - hits[0] > lim.rate_window_s:
        hits.popleft()
    if len(hits) >= lim.rate_limit:
        return False
    hits.append(now)
    return True


@app.middleware("http")
async def _enforce_limits(request: Request, call_next):
    """Reject an over-large body up front (when the client declares its size) and
    rate-limit the upload endpoints per client IP, before any work is done."""
    declared = request.headers.get("content-length")
    if (
        declared is not None
        and declared.isdigit()
        and int(declared) > limits.LIMITS.max_total_bytes
    ):
        return JSONResponse(status_code=413, content={"detail": "request body too large"})
    if request.url.path in _RATE_LIMITED_PATHS and not _rate_ok(request):
        return JSONResponse(status_code=429, content={"detail": "rate limit exceeded; slow down"})
    return await call_next(request)


# Security headers on every response (including the early 413/429 returns above, since this
# middleware is registered later and so wraps the limiter). We deliberately do NOT set a
# restrictive `default-src` Content-Security-Policy: this app also serves the Scalar API-reference
# UI at /scalar, which loads its bundle from a CDN — a strict default-src would break it. We set
# `frame-ancestors 'none'` (the clickjacking-relevant directive) plus the safe transport headers.
_SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "frame-ancestors 'none'",
}


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


@app.exception_handler(limits.UploadRejected)
async def _on_upload_rejected(_request: Request, exc: limits.UploadRejected) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Bounded worker pool for the CPU-bound comparison: numpy releases the GIL on the heavy
# array work, so threads give real parallelism while keeping the event loop responsive.
_COMPARE_EXECUTOR = ThreadPoolExecutor(
    max_workers=limits.LIMITS.max_concurrency, thread_name_prefix="verity-compare"
)


async def _offload(fn, /, *args, **kwargs):
    """Run a CPU-bound comparison in the bounded pool with a wall-clock timeout, so one
    heavy or pathological scan can neither block the loop nor run unbounded."""
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(_COMPARE_EXECUTOR, functools.partial(fn, *args, **kwargs))
    try:
        return await asyncio.wait_for(fut, timeout=limits.LIMITS.compare_timeout_s)
    except TimeoutError as exc:
        raise HTTPException(status_code=503, detail="comparison timed out") from exc


def _surface_from_bytes(data: bytes) -> Surface:
    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        s = verity_x3p.read_x3p(path)
        return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)
    except Exception as exc:  # noqa: BLE001 - surface a clean 400 for a bad upload
        raise HTTPException(status_code=400, detail=f"could not read X3P: {exc}") from exc
    finally:
        os.remove(path)


async def _read_surface(upload: UploadFile) -> Surface:
    budget = limits.ByteBudget(limits.LIMITS.max_total_bytes)
    data = await limits.read_capped(upload, file_cap=limits.LIMITS.max_file_bytes, budget=budget)
    limits.validate_x3p(data, filename=upload.filename or "")
    return _surface_from_bytes(data)


async def _read_marks(
    uploads: list[UploadFile], *, budget: limits.ByteBudget
) -> tuple[list[Surface], list[str]]:
    """Decode each upload and content-hash its raw bytes (the provenance spine that ties
    a report back to the exact scanned file). Reads are size-capped and validated as
    X3P (magic + zip-bomb guard) before they reach the native reader; ``budget`` caps
    the total bytes across the whole request."""
    if len(uploads) > limits.LIMITS.max_files:
        raise limits.TooManyFiles(
            f"{len(uploads)} files exceeds the {limits.LIMITS.max_files}-file limit"
        )
    surfaces: list[Surface] = []
    hashes: list[str] = []
    for f in uploads:
        data = await limits.read_capped(f, file_cap=limits.LIMITS.max_file_bytes, budget=budget)
        limits.validate_x3p(data, filename=f.filename or "")
        surfaces.append(_surface_from_bytes(data))
        hashes.append(hashlib.sha256(data).hexdigest())
    return surfaces, hashes


@app.get(
    "/health",
    tags=["meta"],
    summary="Service health + calibrated domains",
    response_model=HealthResponse,
)
def health() -> dict:
    return {"status": "ok", "engine_version": _engine_version(), "domains": available_domains()}


@app.post(
    "/detect",
    tags=["meta"],
    summary="Suggest a mark type from one scan",
    response_model=DetectResponse,
)
async def detect(scan: UploadFile = File(...)) -> dict:
    """Suggest a mark type for one uploaded scan, from striation anisotropy — the
    structure-tensor coherence of its 2-D FFT power (directional striae → `striated`;
    isotropic areal → `impressed`). The UI pre-selects it; the user confirms, since
    the mark type picks the calibration reference."""
    surface = await _read_surface(scan)
    domain, coherence = detect_domain(surface)
    return {"domain": domain, "coherence": round(coherence, 3)}


_REFUSAL_NOTE = (
    "Verity refused to emit a likelihood ratio: an input falls outside the validated "
    "domain for this reference. A calibrated LR is only meaningful for inputs like the "
    "reference population, so a number here would be invalid rather than merely uncertain. "
    "Re-scan inside the validated domain (resolution, mark type, coverage, signal) and retry."
)

# Only the hard, unrecoverable failures block the comparison: a scan too coarse to
# resolve the roughness band, or the wrong mark type for this reference. Coverage and
# signal shortfalls stay as loud warnings — a masked cartridge scan is legitimately
# sparse, so refusing on coverage would reject valid known-match comparisons.
_HARD_REFUSE_CHECKS = frozenset({"resolution", "modality"})


def _scope_check(surface: Surface, domain: str) -> ScopeReport:
    """Applicability-domain guard for one scan, refusing only on hard failures. A scan
    we cannot even evaluate is treated as out of scope rather than admitted by default."""
    try:
        return check_applicability(
            surface, domain=domain, mode="refuse", blocking=_HARD_REFUSE_CHECKS
        )
    except Exception as exc:  # noqa: BLE001 - cannot establish scope ⇒ refuse, not admit
        return ScopeReport(
            admissible=False,
            mode="refuse",
            domain=domain,
            checks=[],
            overall_reason=f"could not evaluate applicability of this scan: {exc}",
        )


def _refusal_envelope(
    *, domain: str, scope: dict, inadmissible: list[ScopeReport], provenance: dict
) -> dict:
    """The structured out-of-scope result returned instead of a junk LR."""
    reasons = "; ".join(dict.fromkeys(r.overall_reason for r in inadmissible if r.overall_reason))
    return {
        "refused": True,
        "domain": domain,
        "reason": reasons or "one or more inputs are outside the validated domain",
        "scope": scope,
        "scope_note": _REFUSAL_NOTE,
        "provenance": provenance,
    }


_SCORER_CONFIG_KEYS = frozenset(DEFAULT_SCORER_CONFIG.to_dict())


def _coerce_scorer_config(overrides: dict | None) -> ScorerConfig | None:
    """Validate a ``scorer_config`` override dict into a frozen :class:`ScorerConfig` (None
    when absent). Unknown keys and an inverted band raise :class:`ValueError`, so both the
    HTTP path (wrapped to a 400 below) and the in-process MCP tool share one validator."""
    if not overrides:
        return None
    if not isinstance(overrides, dict):
        raise ValueError("scorer_config must be a JSON object")
    unknown = set(overrides) - _SCORER_CONFIG_KEYS
    if unknown:
        raise ValueError(f"unknown scorer_config keys: {sorted(unknown)}")
    merged = {**DEFAULT_SCORER_CONFIG.to_dict(), **overrides}
    merged["cmr_tol"] = tuple(merged["cmr_tol"])
    try:
        cfg = ScorerConfig(**merged)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid scorer_config: {exc}") from exc
    if not cfg.lambda_s < cfg.lambda_c:
        raise ValueError("scorer_config requires lambda_s < lambda_c")
    return cfg


def _parse_scorer_config(raw: str | None) -> ScorerConfig | None:
    """Parse a JSON ``scorer_config`` override into a frozen :class:`ScorerConfig` (None
    when absent). Unknown keys and an inverted band fail fast as 400s, never silently."""
    if not raw:
        return None
    try:
        overrides = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"scorer_config must be JSON: {exc}") from exc
    try:
        return _coerce_scorer_config(overrides)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_UNCALIBRATED_NOTE = (
    "Verity scored this comparison under the requested scorer config but refused to emit a "
    "calibrated likelihood ratio: the bundled reference was built under a different config, "
    "so the query score and the calibration would live on different scales. The raw score is "
    "returned; for an LR, calibrate against a reference built under the requested config."
)


def _uncalibrated_envelope(
    resp: dict, *, domain: str, cfg: ScorerConfig, ref_hash: str | None
) -> dict:
    """The off-config result: the raw score (under the requested config) + attribution +
    scope, but NO calibrated LR — the firewall, on the full-comparison path."""
    keep = (
        "score",
        "score_kind",
        "attribution",
        "attribution_b",
        "previews",
        "scope",
        "provenance",
    )
    return {
        "calibrated": False,
        "domain": domain,
        **{k: resp[k] for k in keep if k in resp},
        "requested_scorer_config_hash": cfg.config_hash,
        "reference_scorer_config_hash": ref_hash,
        "scorer_config": cfg.to_dict(),
        "uncalibrated_reason": _UNCALIBRATED_NOTE,
    }


async def _run_compare(
    domain: str,
    mark_a: list[UploadFile],
    mark_b: list[UploadFile],
    *,
    include: set[str],
    config: ScorerConfig | None = None,
) -> dict:
    """Core comparison shared by the unversioned and ``/v1`` routes. ``include`` selects
    which intermediate computations to attach (empty = lean report). Validation and the
    size-capped reads happen here; the CPU-bound compute is offloaded to a bounded worker
    pool with a wall-clock timeout."""
    if domain not in available_domains():
        raise HTTPException(
            status_code=400,
            detail=f"domain {domain!r} has no calibrated reference; available: {available_domains()}",
        )
    if not mark_a or not mark_b:
        raise HTTPException(status_code=400, detail="provide at least one scan per mark")
    if len(mark_a) + len(mark_b) > limits.LIMITS.max_files:
        raise limits.TooManyFiles(
            f"{len(mark_a) + len(mark_b)} files exceeds the {limits.LIMITS.max_files}-file limit"
        )

    budget = limits.ByteBudget(limits.LIMITS.max_total_bytes)
    surfaces_a, hashes_a = await _read_marks(mark_a, budget=budget)
    surfaces_b, hashes_b = await _read_marks(mark_b, budget=budget)
    provenance = {
        "api_version": app.version,
        "engine_version": _engine_version(),
        "mark_a": [f.filename for f in mark_a],
        "mark_b": [f.filename for f in mark_b],
        "input_hashes": {"mark_a": hashes_a, "mark_b": hashes_b},
    }
    return await _offload(
        _compute_report,
        domain,
        surfaces_a,
        surfaces_b,
        provenance=provenance,
        include=include,
        config=config,
    )


def _compute_report(
    domain: str,
    surfaces_a: list[Surface],
    surfaces_b: list[Surface],
    *,
    provenance: dict,
    include: set[str],
    config: ScorerConfig | None = None,
) -> dict:
    """The synchronous comparison: applicability guard → score → calibrate → assemble.
    Runs in a worker thread, off the event loop."""
    # Applicability-domain guard (refuse mode) on every input, BEFORE scoring — never
    # compute a likelihood ratio for a scan outside the validated domain. The scope
    # annotation rides along on admissible comparisons too (warn-severity notes).
    reports_a = [_scope_check(s, domain) for s in surfaces_a]
    reports_b = [_scope_check(s, domain) for s in surfaces_b]
    scope = {
        "mark_a": [r.to_dict() for r in reports_a],
        "mark_b": [r.to_dict() for r in reports_b],
    }
    inadmissible = [r for r in (*reports_a, *reports_b) if not r.admissible]
    if inadmissible:
        return _refusal_envelope(
            domain=domain, scope=scope, inadmissible=inadmissible, provenance=provenance
        )

    cfg = config or DEFAULT_SCORER_CONFIG
    bundle = load_reference_bundle(domain)
    scores, labels, reference_name = bundle.scores, bundle.labels, bundle.name
    ref_provenance = bundle.provenance
    if domain == "striated":
        if len(surfaces_a) == 1 and len(surfaces_b) == 1:
            single = load_striated_single_bundle()
            ref_provenance = single.provenance
            report, previews = compare_with_previews(
                surfaces_a[0],
                surfaces_b[0],
                domain="striated",
                reference_scores=single.scores,
                reference_labels=single.labels,
                reference_name=single.name,
                provenance={**provenance, "n_lands_a": 1, "n_lands_b": 1},
                cluster_ids=single.cluster_ids,
                config=cfg,
            )
            scores, labels, reference_name = single.scores, single.labels, single.name
        else:
            report, previews = compare_bullets_with_previews(
                surfaces_a,
                surfaces_b,
                reference_scores=scores,
                reference_labels=labels,
                reference_name=reference_name,
                provenance=provenance,
                cluster_ids=bundle.cluster_ids,
                config=cfg,
            )
    else:
        report, previews = compare_with_previews(
            surfaces_a[0],
            surfaces_b[0],
            domain=domain,
            reference_scores=scores,
            reference_labels=labels,
            reference_name=reference_name,
            provenance=provenance,
            cluster_ids=bundle.cluster_ids,
            config=cfg,
        )

    resp = {**report.to_dict(), "previews": previews, "scope": scope}
    # The firewall: a per-request config override that doesn't match the reference's
    # scorer config invalidates the calibration — return the raw score, refuse the LR.
    ref_hash = ref_provenance.get("scorer_config_hash")
    if config is not None and ref_hash and cfg.config_hash != ref_hash:
        return _uncalibrated_envelope(resp, domain=domain, cfg=cfg, ref_hash=ref_hash)
    if domain == "striated" and len(surfaces_a) == 1 and len(surfaces_b) == 1:
        ref = resp["reference"]
        resp["evidence_note"] = {
            "single_land": True,
            "level": "diagnostic_only",
            "reason": (
                "Single-land striated comparison: discrimination on this reference is marginal "
                f"(AUC≈{ref['auc']:.2f}, Cllr≈{ref['cllr']:.2f}), so the likelihood "
                "ratio is diagnostic only — not reportable evidence. Compare all available lands "
                "of the two bullets for a reportable result."
            ),
        }
    if not include:
        return resp

    if "calibration" in include:
        resp["calibration"] = calibration_diagnostics(scores, labels, report.score, reference_name)
    if domain == "striated" and len(surfaces_a) > 1 and len(surfaces_b) > 1:
        resp.update(
            striated_bullet_intermediates(
                surfaces_a, surfaces_b, include, single_land_reference=load_striated_single_land()
            )
        )
    elif domain == "striated" and "trace" in include:
        resp["trace"] = {
            "a": trace_dict(land_trace(surfaces_a[0], lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)),
            "b": trace_dict(land_trace(surfaces_b[0], lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)),
        }
    if "recipe" in include:
        # The reproducible methods-as-JSON + content handle — assembled from the report
        # and the reference's provenance, no new computation.
        recipe = build_recipe(resp, domain=domain, reference_provenance=ref_provenance)
        resp["recipe"] = recipe
        resp["handle"] = recipe["handle"]
    return resp


_COMPARE_EXAMPLE = {
    "domain": "striated",
    "score": 0.153,
    "score_kind": "bullet-contrast",
    "likelihood_ratio": 146.0,
    "log10_lr": 2.16,
    "log10_lr_ci_lo": 1.74,
    "log10_lr_ci_hi": 2.16,
    "lr_ci_method": "bootstrap-clustered",
    "n_sources": 201,
    "direction": "same source",
    "verbal": "moderately strong support for same source",
    "lr_bound_log10": 2.16,
    "lr_bound_hit": True,
    "reference": {
        "name": "pooled bullet-land reference (Hamby-252 & 173, Beretta, Phoenix)",
        "n_km": 146,
        "n_knm": 1755,
        "cllr": 0.193,
        "cllr_min": 0.168,
        "auc": 0.984,
    },
    "attribution": [
        {
            "x": 0,
            "y": 0,
            "w": 40,
            "h": 1,
            "corr": 0.91,
            "x_frac": 0.0,
            "y_frac": 0.0,
            "w_frac": 0.167,
            "h_frac": 1.0,
        }
    ],
    "provenance": {
        "scorer": "bullet-contrast",
        "domain": "striated",
        "input_hashes": {"mark_a": ["<sha256>"], "mark_b": ["<sha256>"]},
    },
    "scope_note": "This is a calibrated weight of evidence on the pooled bullet-land "
    "reference population; it is not a claim about the error rate of "
    "striated examination, which remains unknown.",
    "previews": {"a": "[[…]] downsampled height grids", "b": "[[…]]"},
}


@app.post(
    "/compare",
    tags=["compare"],
    summary="Compare two marks → calibrated likelihood-ratio report",
    responses={200: {"content": {"application/json": {"example": _COMPARE_EXAMPLE}}}},
)
async def compare(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
) -> dict:
    """Compare two marks into a calibrated, bounded **likelihood ratio** with
    region-level attribution. (Lean payload; use `/v1/compare?include=...` for the
    inspectable intermediate computations.)"""
    return await _run_compare(domain, mark_a, mark_b, include=set())


# --- Versioned API (/v1): comparison with inspectable intermediates ---------

v1 = APIRouter(prefix="/v1")


@v1.post(
    "/compare",
    tags=["v1"],
    summary="Compare two marks, optionally returning intermediate computations",
    responses={200: {"content": {"application/json": {"example": _COMPARE_EXAMPLE}}}},
)
async def compare_v1(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
    include: str | None = Form(None),
    scorer_config: str | None = Form(None),
) -> dict:
    """Same calibrated comparison as `/compare`, plus — on request — the algorithm's
    intermediate computations. `include` is a comma-separated subset of:

    - **calibration** — the reference Tippett curve + KM/KNM score histogram with
      this comparison's score located on it (what makes the LR defensible).
    - **features** — the land×land CCF matrix and the structure features the score
      is built from (`diag_contrast`, `offset_margin`, `lag_coherence`, …).
    - **perland** — per-land evidence on the winning diagonal (diagnostic; lands
      are not independent, so the reportable LR is the aggregate).
    - **trace** — the full signature pipeline (raw → bandpassed → oriented →
      signature) for the best-matching land of each bullet.
    - **recipe** — the reproducible *methods section as JSON*: every pipeline step,
      its parameters, the engine version, the input/reference hashes, and a content
      **handle** over the whole recipe (reproducibility as a hash-equality check). On
      by default.

    `include=all` returns everything. The default is `calibration,recipe`. The response
    always carries an applicability-domain `scope` annotation for the inputs.

    `scorer_config` is an optional JSON object of scorer-hyperparameter overrides
    (e.g. `{"lambda_c": 8e-6}`). The comparison is scored under it, but — the firewall —
    if its hash doesn't match the reference's, the calibrated LR is **refused**
    (`calibrated: false`, raw score returned); calibration is valid only on a reference
    built under the same config."""
    return await _run_compare(
        domain,
        mark_a,
        mark_b,
        include=parse_include(include) or {"calibration", "recipe"},
        config=_parse_scorer_config(scorer_config),
    )


@v1.post("/scope", tags=["v1"], summary="Applicability-domain check for one scan")
async def scope_v1(
    scan: UploadFile = File(...),
    domain: str = Form(...),
    mode: str = Form("refuse"),
) -> dict:
    """Check whether one scan is inside the validated domain for `domain`
    (resolution, mark type, coverage, signal). Defaults to `mode=refuse`, which reports
    an out-of-domain scan as `admissible=false` — the basis for refusing a junk LR;
    `mode=warn` annotates only (always `admissible=true`)."""
    if domain not in available_domains():
        raise HTTPException(status_code=400, detail=f"unknown domain {domain!r}")
    if mode not in ("warn", "refuse"):
        raise HTTPException(status_code=400, detail="mode must be 'warn' or 'refuse'")
    surface = await _read_surface(scan)
    return check_applicability(surface, domain=domain, mode=mode).to_dict()


@v1.post(
    "/compare/report.pdf",
    tags=["v1"],
    summary="Court-ready per-comparison PDF report",
    response_class=Response,
)
async def compare_report_pdf(
    domain: str = Form(...),
    mark_a: list[UploadFile] = File(...),
    mark_b: list[UploadFile] = File(...),
    case_id: str | None = Form(None),
    examiner: str | None = Form(None),
) -> Response:
    """Run the comparison and return a court-ready PDF: the calibrated LR with its
    credible interval and verbal weight, the named-scope statement, the reference
    and its cost, the method/pipeline version, the SHA-256 provenance of the input
    scans, and the attribution overlay."""
    report = await _run_compare(domain, mark_a, mark_b, include=set())
    if report.get("refused"):
        raise HTTPException(
            status_code=422,
            detail=report.get("reason", "an input is outside the validated domain"),
        )
    from verity.report_pdf import render_comparison_pdf

    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        render_comparison_pdf(report, path, case_id=case_id, examiner=examiner)
        data = Path(path).read_bytes()
    finally:
        os.remove(path)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=verity-comparison-report.pdf"},
    )


@v1.get("/scorer-config", tags=["v1"], summary="The deployed scorer configuration + hash")
def scorer_config_v1() -> dict:
    """The exact hyperparameters the engine scores with (ISO roughness-band cutoffs, the
    CMR congruence thresholds, the scorer identity) and their content hash. A calibrated
    LR is only valid when a reference's `scorer_config_hash` matches this — so this is the
    value to check before trusting a cross-config comparison."""
    return {**DEFAULT_SCORER_CONFIG.to_dict(), "config_hash": DEFAULT_SCORER_CONFIG.config_hash}


@v1.get("/references", tags=["v1"], summary="List calibrated reference populations + provenance")
def references_v1() -> dict:
    """Every bundled reference the API calibrates against, with the scorer-config hash it
    was built under, its source datasets, and its diagnostics (Cllr/Cllr_min/AUC) — what,
    exactly, each likelihood ratio is calibrated on."""
    return {"references": all_reference_metadata()}


@v1.get("/references/{reference_id}", tags=["v1"], summary="Provenance for one reference")
def reference_v1(reference_id: str) -> dict:
    """Provenance for one reference by id (`striated`, `impressed`, `striated_single`)."""
    meta = reference_metadata(reference_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"unknown reference {reference_id!r}")
    return meta


app.include_router(v1)
app.include_router(steps_router)

# Remote MCP endpoint: the same calibrated tools as the stdio server, hosted. The
# FastMCP app exposes a single route at /mcp; add it to the API router directly (rather
# than mounting under a prefix) so the JSON-RPC endpoint answers at exactly
# https://<host>/mcp with no trailing-slash redirect for clients to follow. Its session
# manager is driven by the app lifespan above (the route's handler closes over it).
app.router.routes.extend(mcp_server.streamable_http_app().routes)


_SCALAR_HTML = """<!doctype html>
<html>
  <head>
    <title>Verity API reference</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
      /* Evidence palette — Scalar custom-theme variables (paper-first). theme:none
         in the config below disables Scalar's built-in presets so these take effect. */
      :root {
        --scalar-color-1: #13243a;            /* ink */
        --scalar-color-2: #5a6677;            /* muted */
        --scalar-color-3: #8a93a3;
        --scalar-color-accent: #0e2a47;       /* navy primary */
        --scalar-background-1: #f4f1ea;       /* canvas / bone */
        --scalar-background-2: #ece7db;       /* panel */
        --scalar-background-3: #e3ddcf;
        --scalar-border-color: rgba(19, 36, 58, 0.14);
        --scalar-button-1: #0e2a47;
        --scalar-button-1-color: #f4f1ea;
        --scalar-color-green: #a9803e;        /* brass — GET */
        --scalar-color-blue: #0e2a47;         /* navy — POST */
        --scalar-color-red: #7a2e2e;          /* oxblood — errors / DELETE */
        --scalar-color-orange: #a9803e;
        --scalar-font: 'Inter', ui-sans-serif, system-ui, sans-serif;
        --scalar-font-code: 'IBM Plex Mono', ui-monospace, monospace;
      }
      .dark-mode {
        --scalar-color-1: #e8e2d4;
        --scalar-color-2: #9aa6b6;
        --scalar-color-accent: #6e97c4;       /* lifted steel — navy is invisible on dark */
        --scalar-background-1: #0c1420;
        --scalar-background-2: #11203b;
        --scalar-background-3: #16263b;
        --scalar-border-color: rgba(232, 226, 212, 0.12);
        --scalar-button-1: #173b5e;
        --scalar-button-1-color: #e8e2d4;
        --scalar-color-green: #c9a063;
        --scalar-color-blue: #6e97c4;
        --scalar-color-red: #c76b6b;
      }
    </style>
  </head>
  <body>
    <script
      id="api-reference"
      data-url="/openapi.json"
      data-configuration='{"theme":"none","darkMode":false}'></script>
    <script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
  </body>
</html>"""


@app.get("/scalar", include_in_schema=False)
def scalar_docs() -> HTMLResponse:
    """A pretty, modern API reference (Scalar), rendered from the OpenAPI schema.
    Swagger UI (/docs) and ReDoc (/redoc) are also available."""
    return HTMLResponse(_SCALAR_HTML)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/scalar")


def run() -> None:
    import uvicorn

    uvicorn.run("verity_api.main:app", host="127.0.0.1", port=8000, reload=False)
