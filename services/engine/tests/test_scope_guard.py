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
    z[::2] = np.nan  # every other row missing → 50% of the extent
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
    z[::2] = np.nan  # every other row missing → 50% of the extent, coverage refuse-severity
    rep = check_applicability(
        s.with_heights(z),
        domain="striated",
        mode="refuse",
        blocking=frozenset({"resolution", "modality"}),
    )
    assert rep.admissible  # coverage no longer blocks the comparison
    assert _check(rep, "coverage").severity == "refuse"  # but the shortfall is recorded


def test_coverage_floor_refuses_near_empty_scan_on_restricted_blocking():
    # Regression: a scan with ~10% measured passed the comparison path because coverage
    # is not a hard check. The coverage floor blocks it even with blocking restricted.
    s = _striated_surface()
    z = np.full_like(s.heights, np.nan)
    z[:, ::10] = s.heights[:, ::10]  # every 10th column → ~10% of the extent
    rep = check_applicability(
        s.with_heights(z),
        domain="striated",
        mode="refuse",
        blocking=frozenset({"resolution", "modality"}),
        coverage_floor=0.25,
    )
    assert _check(rep, "modality").passed  # only coverage can be what blocks here
    assert _check(rep, "coverage").value < 0.25
    assert not rep.admissible
    assert "measured" in rep.overall_reason


def test_coverage_floor_keeps_masked_level_coverage_admissible():
    # 50% coverage (masked-cartridge level) is above the floor: still recorded, not blocking.
    s = _striated_surface()
    z = s.heights.copy()
    z[::2] = np.nan  # 50% of the extent
    rep = check_applicability(
        s.with_heights(z),
        domain="striated",
        mode="refuse",
        blocking=frozenset({"resolution", "modality"}),
        coverage_floor=0.25,
    )
    assert rep.admissible
    assert _check(rep, "coverage").severity == "refuse"


def test_coverage_ignores_empty_export_border():
    # Regression: coverage was the finite fraction of the whole grid, so a fully measured
    # region exported on a mostly empty grid (an uncropped EvoFinder export) read as a
    # few percent. Coverage is now measured within the extent of the finite data.
    s = _striated_surface()
    big = np.full((4 * s.heights.shape[0], 4 * s.heights.shape[1]), np.nan)
    big[: s.heights.shape[0], : s.heights.shape[1]] = s.heights  # 1/16 of the grid
    rep = check_applicability(
        Surface(heights=big, dx=s.dx, dy=s.dy),
        domain="striated",
        mode="refuse",
        blocking=frozenset({"resolution", "modality"}),
        coverage_floor=0.25,
    )
    assert _check(rep, "coverage").passed
    assert _check(rep, "coverage").value == 1.0
    assert rep.admissible


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


def _isotropic_surface(n: int, dx: float = 2e-6, seed: int = 0) -> Surface:
    """Isotropic areal roughness (~0.2 µm, smoothed white noise) → detects impressed,
    resolves the band, full coverage, real signal. ``n`` sets the physical size."""
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(n, n))
    k = np.fft.fftfreq(n)
    kk = np.hypot(*np.meshgrid(k, k))
    z = np.real(np.fft.ifft2(np.fft.fft2(z) * np.exp(-((kk * 2 * np.pi * 3) ** 2) / 2)))
    z *= 0.2e-6 / z.std()
    return Surface(heights=z, dx=dx, dy=dx)


_COMPARE_PATH = dict(
    mode="refuse", blocking=frozenset({"resolution", "modality"}), coverage_floor=0.25
)


def test_small_impressed_scan_is_flagged_not_refused():
    # A firing-pin-sized impressed scan (1.6 mm) detects as impressed like a breech face,
    # but the impressed reference is breech faces only: flag it, never refuse it.
    rep = check_applicability(_isotropic_surface(800), domain="impressed", **_COMPARE_PATH)
    assert _check(rep, "modality").passed  # it really does look impressed
    extent = _check(rep, "extent")
    assert not extent.passed and extent.severity == "warn"
    assert extent.value < 2.5
    assert "breech" in extent.reason and "firing-pin" in extent.reason
    assert rep.admissible  # warn-only


def test_breech_face_sized_impressed_scan_passes_extent():
    rep = check_applicability(_isotropic_surface(1400), domain="impressed", **_COMPARE_PATH)
    extent = _check(rep, "extent")
    assert extent.passed  # 2.8 mm spans a breech face
    assert rep.admissible


def test_extent_check_runs_only_for_impressed():
    rep = check_applicability(_striated_surface(), domain="striated", mode="refuse")
    assert "extent" not in {c.name for c in rep.checks}


def test_extent_measures_finite_data_not_export_grid():
    # A small measured patch on a large, mostly empty export grid is still small: the span
    # is taken over the finite data, as coverage is.
    s = _isotropic_surface(400)  # 0.8 mm patch
    big = np.full((1600, 1600), np.nan)  # 3.2 mm grid
    big[:400, :400] = s.heights
    rep = check_applicability(
        Surface(heights=big, dx=s.dx, dy=s.dy), domain="impressed", **_COMPARE_PATH
    )
    assert not _check(rep, "extent").passed
