"""Applicability-domain scope guard — refuse to emit a likelihood ratio for an
input outside the validated domain.

A calibrated LR is only meaningful for inputs like the reference population it was
calibrated on. A scan at the wrong resolution, of the wrong mark type, or too
sparse/flat to carry striae would still produce a *number* — an invalid one. This
guard checks the input against the domain Verity was validated on and, in
``"refuse"`` mode, returns a structured refusal instead of a junk LR. It is a
direct, operational answer to the critique that methods get applied outside the
domain where they were characterized.

The checks are glass-box and physically motivated:

* **resolution** — the lateral pitch must resolve the individualizing roughness
  band (ISO 16610 short cutoff ``λ_s = 4 µm``; Nyquist wants pitch ≤ 2 µm).
* **modality** — the detected mark type (striae anisotropy) must match the
  requested one, because the mark type picks the calibration reference. A
  hysteresis band flags the ambiguous middle rather than guessing.
* **coverage** — enough of the scan's measured extent (the bounding box of its finite
  data) must be measured (not NaN) to compare; empty export border does not count.
* **signal** — the roughness band must carry real amplitude (not a flat/polished
  or mis-acquired surface).
* **extent** (impressed only, warn-only) — the measured area must span a breech face.
  The impressed reference is breech faces only; a firing-pin impression (a crater
  about 1-2 mm across) is detected as impressed too, so a scan smaller than a breech
  face is flagged as one the reference may not cover. It never refuses.

Thresholds here are physically-motivated defaults; :func:`applicability_thresholds`
derives data-driven ones from a low percentile of the in-domain reference (the
defensible story), to be bundled per reference. Two modes: ``"warn"`` annotates
only (every scan stays admissible — useful while a reference still lacks its
calibrated thresholds), while ``"refuse"`` returns a structured refusal when a
blocking check fails. The hosted API runs ``"refuse"`` mode on its comparison
path, blocking on the hard, unrecoverable failures (resolution, modality) and
keeping coverage/signal shortfalls as non-blocking warnings, except that coverage
below a hard floor (``coverage_floor``) still refuses.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field

import numpy as np

from ..detect import detect_domain
from ..preprocess import isolate_roughness, remove_form
from ..surface import Surface
from .scorer_config import DEFAULT_SCORER_CONFIG

logger = logging.getLogger(__name__)

# Striated roughness band (m) — sourced from the one scorer config so the guard and the
# comparison pipeline can never drift apart.
_LAMBDA_S, _LAMBDA_C = DEFAULT_SCORER_CONFIG.lambda_s, DEFAULT_SCORER_CONFIG.lambda_c
# Coherence threshold separating striated/impressed, with a hysteresis half-width.
_COH_THRESHOLD, _COH_BAND = 0.6, 0.1


@dataclass(frozen=True)
class ScopeCheck:
    """One applicability check. ``severity`` is ``"ok"`` when passed, else
    ``"refuse"`` (would block in refuse mode) or ``"warn"`` (annotate only)."""

    name: str
    passed: bool
    severity: str
    value: float
    threshold: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ScopeReport:
    """The applicability decision for one scan."""

    admissible: bool
    mode: str  # "warn" | "refuse"
    domain: str
    checks: list[ScopeCheck] = field(default_factory=list)
    overall_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "admissible": self.admissible,
            "mode": self.mode,
            "domain": self.domain,
            "checks": [c.to_dict() for c in self.checks],
            "overall_reason": self.overall_reason,
        }


def _resolution_check(surface: Surface, reference_meta: dict | None) -> ScopeCheck:
    pitch_um = float(max(abs(surface.dx), abs(surface.dy)) * 1e6)
    nyquist_um = _LAMBDA_S / 2 * 1e6  # 2.0 µm
    cannot_resolve_um = _LAMBDA_S * 1e6  # 4.0 µm
    if pitch_um > cannot_resolve_um:
        return ScopeCheck(
            "resolution",
            False,
            "refuse",
            pitch_um,
            nyquist_um,
            f"lateral pitch {pitch_um:.2f} µm exceeds λ_s = {cannot_resolve_um:.0f} µm; "
            "the individualizing roughness band cannot be resolved",
        )
    if pitch_um > nyquist_um:
        return ScopeCheck(
            "resolution",
            False,
            "warn",
            pitch_um,
            nyquist_um,
            f"lateral pitch {pitch_um:.2f} µm is above Nyquist for λ_s ({nyquist_um:.0f} µm); "
            "the roughness band is only marginally resolved",
        )
    # Optional: compare against the reference's calibrated pitch band.
    if reference_meta and "pitch_um" in reference_meta:
        lo, hi = reference_meta["pitch_um"]
        if not (0.5 * lo <= pitch_um <= 2.0 * hi):
            return ScopeCheck(
                "resolution",
                False,
                "warn",
                pitch_um,
                float(hi),
                f"lateral pitch {pitch_um:.2f} µm is outside the reference band "
                f"[{lo:.2f}, {hi:.2f}] µm",
            )
    return ScopeCheck(
        "resolution", True, "ok", pitch_um, nyquist_um, "pitch resolves the roughness band"
    )


def _modality_check(surface: Surface, requested_domain: str | None) -> tuple[ScopeCheck, str]:
    detected, coherence = detect_domain(surface)
    # detect_domain distinguishes the surface *physics* (striated vs impressed); a
    # toolmark is physically striated, so requesting the toolmark reference expects a
    # striated detection.
    expected = "striated" if requested_domain == "toolmark" else requested_domain
    if requested_domain is None or detected == expected:
        return (
            ScopeCheck(
                "modality",
                True,
                "ok",
                float(coherence),
                _COH_THRESHOLD,
                f"detected {detected} (coherence {coherence:.2f})",
            ),
            detected,
        )
    ambiguous = abs(coherence - _COH_THRESHOLD) <= _COH_BAND
    severity = "warn" if ambiguous else "refuse"
    reason = (
        f"requested {requested_domain} but the scan looks {detected} "
        f"(coherence {coherence:.2f}); the {requested_domain} reference may not apply"
    )
    if ambiguous:
        reason += " — mark type is ambiguous, confirm before relying on the LR"
    return (
        ScopeCheck("modality", False, severity, float(coherence), _COH_THRESHOLD, reason),
        detected,
    )


def _measured_extent_fraction(mask: np.ndarray) -> float:
    """Fraction of the measured extent that is actually measured: the share of finite
    points inside the bounding box of the finite data. Instruments export masked regions
    on grids of very different sizes (an uncropped EvoFinder export is mostly empty
    border), so counting over the whole grid measures the export, not the data."""
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size == 0:
        return 0.0
    cols = np.flatnonzero(mask.any(axis=0))
    box = mask[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
    return float(box.mean())


def _coverage_check(surface: Surface) -> ScopeCheck:
    frac = _measured_extent_fraction(surface.mask)
    if frac < 0.6:
        return ScopeCheck(
            "coverage",
            False,
            "refuse",
            frac,
            0.6,
            f"only {frac:.0%} of the scan is measured; too sparse to compare",
        )
    if frac < 0.8:
        return ScopeCheck(
            "coverage",
            False,
            "warn",
            frac,
            0.8,
            f"{frac:.0%} of the scan is measured; missing data may weaken the comparison",
        )
    return ScopeCheck("coverage", True, "ok", frac, 0.8, f"{frac:.0%} of the scan is measured")


def _signal_check(surface: Surface) -> ScopeCheck:
    """RMS amplitude in the isolated roughness band (nm). A flat/polished or
    mis-acquired surface has near-zero band amplitude and cannot carry striae."""
    try:
        rough = isolate_roughness(remove_form(surface, degree=2), _LAMBDA_S, _LAMBDA_C)
        z = rough.heights
        finite = z[np.isfinite(z)]
        sq_nm = float(np.sqrt(np.mean(finite**2)) * 1e9) if finite.size else 0.0
    except Exception:  # noqa: BLE001 - a surface we cannot even filter is out of scope
        logger.exception("could not isolate a roughness band; marking scan out of scope")
        return ScopeCheck(
            "signal", False, "warn", 0.0, 20.0, "could not isolate a roughness band from this scan"
        )
    if sq_nm < 2.0:
        return ScopeCheck(
            "signal",
            False,
            "refuse",
            sq_nm,
            20.0,
            f"roughness-band amplitude {sq_nm:.1f} nm is negligible; the surface is "
            "effectively flat (polished or mis-acquired)",
        )
    if sq_nm < 20.0:
        return ScopeCheck(
            "signal",
            False,
            "warn",
            sq_nm,
            20.0,
            f"roughness-band amplitude {sq_nm:.1f} nm is low; weak individualizing texture",
        )
    return ScopeCheck("signal", True, "ok", sq_nm, 20.0, f"roughness-band amplitude {sq_nm:.1f} nm")


# Smallest span (mm) of the measured area expected of a breech face. The impressed
# reference (Fadul) is breech faces only. A firing-pin impression is a crater about
# 1-2 mm across, and detect_domain calls it impressed too, so without this it would be
# calibrated as a breech face. The 40 Fadul reference scans span 3.72-4.03 mm; on the
# EvoFinder pilot, firing-pin masks spanned 0.86-1.86 mm and breech-face masks 3.0-3.6 mm.
_IMPRESSED_MIN_SPAN_MM = 2.5


def _measured_span_mm(surface: Surface) -> float:
    """Longer side (mm) of the bounding box of the scan's finite data: how far the
    measured area reaches, independent of export border and of masked holes inside it."""
    mask = surface.mask
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size == 0:
        return 0.0
    cols = np.flatnonzero(mask.any(axis=0))
    height = (rows[-1] - rows[0] + 1) * abs(surface.dy)
    width = (cols[-1] - cols[0] + 1) * abs(surface.dx)
    return float(max(height, width) * 1e3)


def _extent_check(surface: Surface) -> ScopeCheck:
    """Warn-only: an impressed scan smaller than a breech face is probably a firing-pin
    impression, which the breech-face-only reference was not calibrated on."""
    span = _measured_span_mm(surface)
    if span < _IMPRESSED_MIN_SPAN_MM:
        return ScopeCheck(
            "extent",
            False,
            "warn",
            span,
            _IMPRESSED_MIN_SPAN_MM,
            f"measured area spans only {span:.2f} mm, smaller than a breech face; this may "
            "be a firing-pin impression, and the impressed reference is calibrated on breech "
            "faces only, so the likelihood ratio may not apply",
        )
    return ScopeCheck(
        "extent",
        True,
        "ok",
        span,
        _IMPRESSED_MIN_SPAN_MM,
        f"measured area spans {span:.2f} mm (breech-face sized)",
    )


def check_applicability(
    surface: Surface,
    *,
    domain: str,
    reference_meta: dict | None = None,
    requested_domain: str | None = None,
    mode: str = "warn",
    blocking: frozenset[str] | None = None,
    coverage_floor: float | None = None,
) -> ScopeReport:
    """Check one scan against the validated domain.

    ``mode="warn"`` always returns ``admissible=True`` and only annotates;
    ``mode="refuse"`` returns ``admissible=False`` if a *blocking* ``"refuse"``-severity
    check fails. ``blocking`` names which checks can block (``None`` = all four — the
    strict default used by ``/v1/scope``); pass e.g. ``frozenset({"resolution",
    "modality"})`` to refuse only on the hard, unrecoverable failures while leaving
    coverage/signal shortfalls as non-blocking warnings (a masked cartridge scan is
    legitimately sparse, so coverage should warn, not refuse, on the comparison path).
    ``requested_domain`` (defaults to ``domain``) is the mark type the caller intends to
    compare under, used by the modality check.

    ``coverage_floor`` (refuse mode only) is a hard floor on measured coverage that
    blocks even when ``"coverage"`` is not in ``blocking``: a scan with almost nothing
    measured cannot be compared, however legitimately masked. Coverage between the
    floor and the usual 60% line still records a refuse-severity check without blocking."""
    if mode not in ("warn", "refuse"):
        raise ValueError(f"mode must be 'warn' or 'refuse', got {mode!r}")
    requested = requested_domain or domain
    res = _resolution_check(surface, reference_meta)
    modality, _detected = _modality_check(surface, requested)
    cov = _coverage_check(surface)
    sig = _signal_check(surface)
    checks = [res, modality, cov, sig]
    if requested == "impressed":
        checks.append(_extent_check(surface))  # warn-only: never blocks

    failed = [c for c in checks if not c.passed]
    would_refuse = [
        c
        for c in failed
        if c.severity == "refuse"
        and (
            blocking is None
            or c.name in blocking
            or (c.name == "coverage" and coverage_floor is not None and c.value < coverage_floor)
        )
    ]
    admissible = True if mode == "warn" else not would_refuse
    if not failed:
        overall = "in scope: the scan matches the validated domain"
    else:
        blocking = would_refuse if (mode == "refuse" and would_refuse) else failed
        overall = "; ".join(c.reason for c in blocking)
    return ScopeReport(
        admissible=admissible, mode=mode, domain=domain, checks=checks, overall_reason=overall
    )


def applicability_thresholds(surfaces: list[Surface], *, percentile: float = 2.0) -> dict:
    """Data-driven thresholds from in-domain reference scans: the coverage and
    roughness-amplitude floors at a low percentile of the validated population, and
    the observed lateral-pitch band. Bundle the result per reference so the gate is
    derived from the data it protects, not hand-picked."""
    pitches, covs, sqs = [], [], []
    for s in surfaces:
        pitches.append(float(max(abs(s.dx), abs(s.dy)) * 1e6))
        covs.append(_measured_extent_fraction(s.mask))
        rough = isolate_roughness(remove_form(s, degree=2), _LAMBDA_S, _LAMBDA_C)
        finite = rough.heights[np.isfinite(rough.heights)]
        sqs.append(float(np.sqrt(np.mean(finite**2)) * 1e9) if finite.size else 0.0)
    return {
        "pitch_um": [float(np.min(pitches)), float(np.max(pitches))],
        "coverage_floor": float(np.percentile(covs, percentile)),
        "signal_floor_nm": float(np.percentile(sqs, percentile)),
        "n_reference": len(surfaces),
    }
