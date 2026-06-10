"""Tests for the applicability-domain scope guard."""

from __future__ import annotations

import json

import numpy as np

from verity.decision.scope_guard import check_applicability
from verity.surface import Surface


def _striated_surface(nx: int = 256, ny: int = 256, dx: float = 1.5e-6) -> Surface:
    """Anisotropic vertical striae with real (~0.5 µm) amplitude → detects as
    striated, resolves the band, full coverage, real signal."""
    rng = np.random.default_rng(0)
    x = np.arange(nx)
    stripes = 0.5e-6 * np.sin(2 * np.pi * x / 12.0)
    z = np.tile(stripes, (ny, 1)) + rng.normal(scale=0.03e-6, size=(ny, nx))
    return Surface(heights=z, dx=dx, dy=dx)


def _flat_surface(nx: int = 256, ny: int = 256, dx: float = 1.5e-6) -> Surface:
    """Near-flat, isotropic, sub-nm amplitude → detects impressed, no real signal."""
    rng = np.random.default_rng(1)
    return Surface(heights=rng.normal(scale=1e-10, size=(ny, nx)), dx=dx, dy=dx)


def _check(report, name):
    return next(c for c in report.checks if c.name == name)


def test_good_surface_is_admissible():
    s = _striated_surface()
    rep = check_applicability(s, domain="striated", mode="refuse")
    assert rep.admissible
    assert _check(rep, "resolution").passed
    assert _check(rep, "coverage").passed
    assert _check(rep, "signal").passed


def test_coarse_pitch_is_refused():
    s = _striated_surface(dx=5e-6)  # > λ_s = 4 µm
    rep = check_applicability(s, domain="striated", mode="refuse")
    assert not rep.admissible
    res = _check(rep, "resolution")
    assert not res.passed and res.severity == "refuse"


def test_low_coverage_is_refused():
    s = _striated_surface()
    z = s.heights.copy()
    z[: z.shape[0] // 2] = np.nan  # 50% missing
    rep = check_applicability(s.with_heights(z), domain="striated", mode="refuse")
    assert not rep.admissible
    assert _check(rep, "coverage").severity == "refuse"


def test_modality_mismatch_is_refused():
    s = _striated_surface()  # clearly striated
    rep = check_applicability(s, domain="impressed", requested_domain="impressed", mode="refuse")
    assert not rep.admissible
    assert _check(rep, "modality").severity == "refuse"


def test_flat_surface_signal_refused():
    s = _flat_surface()
    rep = check_applicability(s, domain="impressed", requested_domain="impressed", mode="refuse")
    # flat isotropic surface: modality matches (impressed) but no roughness signal
    assert _check(rep, "signal").severity == "refuse"
    assert not rep.admissible


def test_blocking_limits_refusal_to_named_checks():
    # Low coverage is a refuse-severity failure, but with blocking restricted to the
    # hard checks the comparison stays admissible (coverage becomes a warning). This is
    # what keeps a legitimately-masked cartridge scan from being rejected.
    s = _striated_surface()
    z = s.heights.copy()
    z[: z.shape[0] // 2] = np.nan  # 50% missing → coverage refuse-severity
    rep = check_applicability(
        s.with_heights(z),
        domain="striated",
        mode="refuse",
        blocking=frozenset({"resolution", "modality"}),
    )
    assert rep.admissible  # coverage no longer blocks the comparison
    assert _check(rep, "coverage").severity == "refuse"  # but the shortfall is recorded


def test_blocking_still_refuses_named_hard_failures():
    s = _striated_surface(dx=5e-6)  # coarse pitch → resolution refuse
    rep = check_applicability(
        s, domain="striated", mode="refuse", blocking=frozenset({"resolution", "modality"})
    )
    assert not rep.admissible
    assert _check(rep, "resolution").severity == "refuse"


def test_warn_mode_never_blocks_but_records_failures():
    s = _striated_surface(dx=5e-6)
    rep = check_applicability(s, domain="striated", mode="warn")
    assert rep.admissible  # warn mode annotates, never blocks
    assert _check(rep, "resolution").severity == "refuse"  # but the failure is recorded
    assert "exceeds" in rep.overall_reason
    json.dumps(rep.to_dict())  # serializable for the API


def test_toolmark_domain_expects_striated_physics():
    """Requesting the toolmark reference on a striated scan passes the modality
    check (a toolmark IS striated physics); on an isotropic scan it refuses the
    same way a striated request would."""
    from verity.decision.scope_guard import check_applicability

    report = check_applicability(_striated_surface(), domain="toolmark")
    modality = _check(report, "modality")
    assert modality.passed, modality.reason

    striated_eq = check_applicability(_striated_surface(), domain="striated")
    assert _check(striated_eq, "modality").passed == modality.passed
