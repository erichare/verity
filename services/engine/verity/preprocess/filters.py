"""ISO 16610 Gaussian areal filtering and the roughness-band isolation that
turns a raw surface into the *individualizing* texture the comparison uses.

The ISO 16610 Gaussian weighting function has 50 % transmission at the cutoff
wavelength ``λ``; that fixes the relationship between ``λ`` and the Gaussian
standard deviation: ``σ = α·λ / √(2π)`` with ``α = √(ln2/π)`` (so
``σ ≈ 0.1874·λ``). A low-pass with cutoff ``λ`` therefore transmits a sinusoid
of wavelength ``λ`` at exactly half amplitude.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from ..surface import Surface

# ISO 16610 Gaussian filter constant.
_ALPHA = np.sqrt(np.log(2.0) / np.pi)


def _sigma_px(cutoff: float, pixel_size: float) -> float:
    """Gaussian σ in pixels for an ISO 16610 cutoff wavelength."""
    return _ALPHA * cutoff / np.sqrt(2.0 * np.pi) / pixel_size


def gaussian_lowpass(surface: Surface, cutoff: float) -> Surface:
    """ISO 16610 Gaussian low-pass at wavelength ``cutoff`` (length units),
    NaN-aware via normalized convolution so invalid points neither contribute
    nor are filled. Keeps wavelengths longer than ``cutoff``.
    """
    z = surface.heights
    mask = ~np.isnan(z)
    sigma = (_sigma_px(cutoff, surface.dy), _sigma_px(cutoff, surface.dx))

    filled = np.where(mask, z, 0.0)
    weight = mask.astype(np.float64)
    num = gaussian_filter(filled, sigma=sigma, mode="nearest")
    den = gaussian_filter(weight, sigma=sigma, mode="nearest")

    out = np.full_like(z, np.nan)
    good = den > 1e-9
    out[good] = num[good] / den[good]
    out[~mask] = np.nan
    return surface.with_heights(out)


def isolate_roughness(surface: Surface, lambda_s: float, lambda_c: float) -> Surface:
    """Bandpass to the individualizing roughness band: an **S-filter** (low-pass
    at ``lambda_s`` to drop measurement noise) followed by an **L-filter**
    (subtract the ``lambda_c`` mean line to drop waviness/form). Returns the
    height residual in the band ``[lambda_s, lambda_c]``.
    """
    if not lambda_s < lambda_c:
        raise ValueError(f"need lambda_s < lambda_c, got {lambda_s} >= {lambda_c}")
    smoothed = gaussian_lowpass(surface, lambda_s)
    mean_line = gaussian_lowpass(smoothed, lambda_c)
    roughness = smoothed.heights - mean_line.heights
    return surface.with_heights(roughness)


def sa(surface: Surface) -> float:
    """Arithmetic mean height ``Sa`` (ISO 25178), over valid points."""
    return float(np.nanmean(np.abs(surface.heights - np.nanmean(surface.heights))))


def sq(surface: Surface) -> float:
    """Root-mean-square height ``Sq`` (ISO 25178), over valid points."""
    return float(np.sqrt(np.nanmean((surface.heights - np.nanmean(surface.heights)) ** 2)))
