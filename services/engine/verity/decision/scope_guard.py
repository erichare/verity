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
* **coverage** — enough of the scan must be measured (not NaN) to compare.
* **signal** — the roughness band must carry real amplitude (not a flat/polished
  or mis-acquired surface).

Thresholds here are physically-motivated defaults; :func:`applicability_thresholds`
derives data-driven ones from a low percentile of the in-domain reference (the
defensible story), to be bundled per reference. Until those sidecars exist the
guard ships in ``"warn"`` mode (annotate, don't block); flip to ``"refuse"`` once
each reference carries its calibrated band.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from ..detect import detect_domain
from ..preprocess import isolate_roughness, remove_form
from ..surface import Surface
from .scorer_config import DEFAULT_SCORER_CONFIG

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
    if requested_domain is None or detected == requested_domain:
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


def _coverage_check(surface: Surface) -> ScopeCheck:
    frac = float(surface.mask.mean())
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


def check_applicability(
    surface: Surface,
    *,
    domain: str,
    reference_meta: dict | None = None,
    requested_domain: str | None = None,
    mode: str = "warn",
    blocking: frozenset[str] | None = None,
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
    compare under, used by the modality check."""
    if mode not in ("warn", "refuse"):
        raise ValueError(f"mode must be 'warn' or 'refuse', got {mode!r}")
    requested = requested_domain or domain
    res = _resolution_check(surface, reference_meta)
    modality, _detected = _modality_check(surface, requested)
    cov = _coverage_check(surface)
    sig = _signal_check(surface)
    checks = [res, modality, cov, sig]

    failed = [c for c in checks if not c.passed]
    would_refuse = [
        c
        for c in failed
        if c.severity == "refuse" and (blocking is None or c.name in blocking)
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
        covs.append(float(s.mask.mean()))
        rough = isolate_roughness(remove_form(s, degree=2), _LAMBDA_S, _LAMBDA_C)
        finite = rough.heights[np.isfinite(rough.heights)]
        sqs.append(float(np.sqrt(np.mean(finite**2)) * 1e9) if finite.size else 0.0)
    return {
        "pitch_um": [float(np.min(pitches)), float(np.max(pitches))],
        "coverage_floor": float(np.percentile(covs, percentile)),
        "signal_floor_nm": float(np.percentile(sqs, percentile)),
        "n_reference": len(surfaces),
    }
