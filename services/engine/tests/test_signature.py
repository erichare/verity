import numpy as np

from verity import Surface, align_1d, dominant_orientation, striation_signature


def _striae(nx: int, ny: int, direction_deg: float, wavelength: float = 10.0) -> np.ndarray:
    """A striated field whose striae run along ``direction_deg``."""
    yy, xx = np.mgrid[0:ny, 0:nx].astype(float)
    a = np.radians(direction_deg)
    kx, ky = np.cos(a + np.pi / 2), np.sin(a + np.pi / 2)  # wavevector ⟂ striae
    return np.sin(2 * np.pi * (kx * xx + ky * yy) / wavelength)


def _ang_dist_deg(a: float, b: float) -> float:
    d = abs((a - b) % 180.0)
    return min(d, 180.0 - d)


def test_orientation_vertical_striae():
    s = Surface(heights=_striae(120, 100, 90.0), dx=1.0, dy=1.0)
    ang = np.degrees(dominant_orientation(s))
    assert _ang_dist_deg(ang, 90.0) < 8.0


def test_orientation_horizontal_striae():
    s = Surface(heights=_striae(120, 100, 0.0), dx=1.0, dy=1.0)
    ang = np.degrees(dominant_orientation(s))
    assert _ang_dist_deg(ang, 0.0) < 8.0


def test_signature_recovers_striation_profile():
    nx, ny = 200, 80
    x = np.arange(nx)
    profile = np.sin(2 * np.pi * x / 12.0) + 0.4 * np.sin(2 * np.pi * x / 5.0)
    s = Surface(heights=np.tile(profile, (ny, 1)), dx=1.0, dy=1.0)  # vertical striae

    sig = striation_signature(s, orient=False)

    corr = np.corrcoef(sig - np.nanmean(sig), profile - profile.mean())[0, 1]
    assert corr > 0.95


def test_signature_orientation_invariant_for_vertical():
    nx, ny = 200, 120
    x = np.arange(nx)
    profile = np.sin(2 * np.pi * x / 12.0)
    s = Surface(heights=np.tile(profile, (ny, 1)), dx=1.0, dy=1.0)

    # The Stage-0 path FFT-orients then groove-crops. With the crop off (keep=1)
    # the orientation alone must recover the profile; with the default crop the
    # signature is a shorter inner-band slice.
    full = striation_signature(s, orient=True, keep=1.0)
    assert align_1d(full, profile)[1] > 0.95
    cropped = striation_signature(s, orient=True)
    assert len(cropped) < len(full)  # groove shoulders dropped
