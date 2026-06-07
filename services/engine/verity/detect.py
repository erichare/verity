"""Heuristic mark-type detection from surface anisotropy.

Striated marks (bullet lands, toolmarks) are dominated by parallel striae — their
2-D FFT power concentrates along one direction. Impressed / areal marks (cartridge
breech faces) have no single striation axis, so their power is more isotropic. The
structure-tensor coherence of the power spectrum separates the two.

This is a *suggestion* the UI pre-selects and the user confirms: the mark type also
picks the calibration reference population, which is the scientifically load-bearing
choice — a wrong guess must not silently produce an invalid likelihood ratio.
"""

from __future__ import annotations

import numpy as np

from .preprocess import remove_form
from .surface import Surface

# Coherence at/above this -> striated. Calibrated on real data: Hamby bullet lands
# score ~0.77-0.97; areal/isotropic surfaces score <0.5.
_THRESHOLD = 0.6


def directional_coherence(z: np.ndarray, w: np.ndarray) -> float:
    """Structure-tensor coherence of the 2-D FFT power spectrum, in [0, 1]. ~1 when
    the surface is dominated by one striation direction, ~0 when it is isotropic."""
    g = np.nan_to_num(z) * w
    if (w > 0).any():
        g = g - g[w > 0].mean()
    g = g * np.outer(np.hanning(g.shape[0]), np.hanning(g.shape[1]))
    power = np.abs(np.fft.fftshift(np.fft.fft2(g))) ** 2
    cy, cx = np.array(power.shape) // 2
    yy, xx = np.mgrid[: power.shape[0], : power.shape[1]]
    yy, xx = yy - cy, xx - cx
    r = np.hypot(yy, xx)
    rmax = max(min(cy, cx), 1)
    band = (r > 0.04 * rmax) & (r < 0.5 * rmax)  # drop DC/grooves + the rectangular-edge cross
    pm = power * band
    total = pm.sum() + 1e-12
    ixx = (pm * xx * xx).sum() / total
    iyy = (pm * yy * yy).sum() / total
    ixy = (pm * xx * yy).sum() / total
    return float(np.sqrt((ixx - iyy) ** 2 + 4.0 * ixy**2) / (ixx + iyy + 1e-12))


def detect_domain(surface: Surface) -> tuple[str, float]:
    """Suggest a mark type from striation anisotropy.

    Returns ``(domain, coherence)`` where ``domain`` is ``"striated"`` or
    ``"impressed"`` and ``coherence`` is the [0, 1] anisotropy it was decided on.
    """
    leveled = remove_form(surface, degree=2)
    z = leveled.heights
    w = (~np.isnan(z)).astype(np.float64)
    coherence = directional_coherence(z, w)
    return ("striated" if coherence >= _THRESHOLD else "impressed"), coherence
