import numpy as np

from verity import Surface, gaussian_lowpass, isolate_roughness, remove_form


def _rows(profile: np.ndarray, n: int = 8) -> np.ndarray:
    return np.asarray(profile, float)[None, :].repeat(n, axis=0)


def _amp(row: np.ndarray) -> float:
    """Amplitude of a (near-)sinusoid from its RMS."""
    return float(np.sqrt(2.0) * np.std(row))


def test_remove_form_recovers_texture():
    ny, nx = 60, 80
    yy, xx = np.mgrid[0:ny, 0:nx].astype(float)
    form = 3.0 + 0.5 * xx - 0.2 * yy + 0.001 * xx**2 + 0.002 * yy**2
    texture = 0.1 * np.sin(2 * np.pi * xx / 4.0)
    s = Surface(heights=form + texture, dx=1e-6, dy=1e-6)

    r = remove_form(s, degree=2)

    centered_texture = texture - texture.mean()
    assert np.nanstd(r.heights - centered_texture) < 1e-2
    assert abs(np.nanmean(r.heights)) < 1e-6


def test_gaussian_lowpass_is_half_amplitude_at_cutoff():
    nx, cutoff = 4000, 40.0
    x = np.arange(nx)
    s = Surface(heights=_rows(np.sin(2 * np.pi * x / cutoff)), dx=1.0, dy=1.0)

    lp = gaussian_lowpass(s, cutoff)

    mid = lp.heights[4, nx // 4 : 3 * nx // 4]
    assert 0.43 < _amp(mid) < 0.57  # ISO: 50% transmission at the cutoff


def test_gaussian_lowpass_passes_long_attenuates_short():
    nx, cutoff = 4000, 40.0
    x = np.arange(nx)
    long_wave = np.sin(2 * np.pi * x / (cutoff * 8))
    short_wave = np.sin(2 * np.pi * x / (cutoff / 8))
    s = Surface(heights=_rows(long_wave + short_wave), dx=1.0, dy=1.0)

    lp = gaussian_lowpass(s, cutoff)

    mid = lp.heights[4, nx // 4 : 3 * nx // 4]
    assert 0.9 < _amp(mid) < 1.1  # long wave preserved, short wave gone


def test_filter_is_nan_aware():
    z = np.ones((20, 20))
    z[5, 5] = np.nan
    s = Surface(heights=z, dx=1.0, dy=1.0)

    lp = gaussian_lowpass(s, 5.0)

    assert np.isnan(lp.heights[5, 5])  # invalid stays invalid
    assert np.isfinite(lp.heights[0, 0])


def test_isolate_roughness_keeps_in_band_drops_noise_and_waviness():
    nx, lam_s, lam_c = 4000, 8.0, 200.0
    x = np.arange(nx)
    noise = 0.5 * np.sin(2 * np.pi * x / (lam_s / 3))  # < λs -> removed
    rough = 1.0 * np.sin(2 * np.pi * x / 40.0)  # in band -> kept
    waviness = 2.0 * np.sin(2 * np.pi * x / (lam_c * 3))  # > λc -> removed
    s = Surface(heights=_rows(noise + rough + waviness), dx=1.0, dy=1.0)

    band = isolate_roughness(s, lam_s, lam_c)

    mid = band.heights[4, nx // 4 : 3 * nx // 4]
    assert 0.85 < _amp(mid) < 1.15  # only the in-band amplitude-1 component
