"""Areal (impressed-mark) comparison — the breech-face / cartridge-case path.

Where the striated path (:mod:`verity.region` + 1-D cross-correlation) handles
parallel-line marks (bullet lands, toolmarks), this handles 2-D **impressed**
marks: cartridge-case breech-face impressions, the negative of the gun's breech
stamped into the primer. The metrology is the *same* — form removal (the primer
is curved) + ISO roughness isolation — and only the comparison changes: an areal
score, the peak 2-D **normalized cross-correlation over a rotation grid** (the
classic breech-face similarity; cartridge cases sit at arbitrary rotation).

One representation crossing the striated <-> impressed physics divide is Verity's
central scientific bet. On the Fadul 10-consecutively-manufactured-slide set (the
hardest benchmark) this reaches slide-disjoint AUC ~0.94 with zero impressed-mark
tuning — the same metrology that did bullet lands.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import rotate

from .preprocess import isolate_roughness, remove_form
from .surface import Surface

DEFAULT_LAMBDA_S = 4e-6  # drop measurement noise (m)
DEFAULT_LAMBDA_C = 150e-6  # drop primer form/waviness (m)
DEFAULT_DECIMATE = 5  # speed: breech-face maps are ~1200px
DEFAULT_SIZE = 256  # common square for the FFT cross-correlation
DEFAULT_ANGLES = tuple(range(0, 360, 10))  # rotation search (deg)


def areal_signature(
    surface: Surface,
    *,
    lambda_s: float = DEFAULT_LAMBDA_S,
    lambda_c: float = DEFAULT_LAMBDA_C,
    decimate: int = DEFAULT_DECIMATE,
    size: int = DEFAULT_SIZE,
) -> np.ndarray:
    """A breech-face surface → a fixed-size, zero-mean, unit-norm roughness map
    (invalid/masked pixels are zero). Form removal + roughness isolation are the
    same operators the striated path uses; the result is the areal comparison
    object for :func:`areal_score`."""
    s = remove_form(surface, degree=2)
    s = isolate_roughness(s, lambda_s, lambda_c)
    r = s.heights[::decimate, ::decimate]
    out = np.full((size, size), np.nan)
    h, w = min(r.shape[0], size), min(r.shape[1], size)
    out[:h, :w] = r[:h, :w]
    mask = np.isfinite(out)
    z = np.zeros((size, size))
    if mask.sum() > 10:
        z[mask] = out[mask] - out[mask].mean()
        norm = np.linalg.norm(z)
        if norm > 1e-12:
            z /= norm
    return z


def _ccf_peak(a: np.ndarray, b: np.ndarray) -> float:
    """Peak normalized cross-correlation over all translations (FFT). With ``a``,
    ``b`` zero-mean unit-norm, the peak is a cosine similarity at the best shift."""
    spectrum = np.fft.rfft2(a) * np.conj(np.fft.rfft2(b))
    return float(np.fft.irfft2(spectrum, a.shape).max())


def areal_score(a: np.ndarray, b: np.ndarray, *, angles=DEFAULT_ANGLES) -> float:
    """Similarity of two :func:`areal_signature` maps: the peak normalized
    cross-correlation maximized over translation (FFT) and a rotation grid.
    Higher = more same-source. ``a`` is assumed unit-norm; each rotated ``b`` is
    re-normalized over its support."""
    best = -1.0
    for theta in angles:
        rotated = rotate(b, float(theta), reshape=False, order=1)
        norm = np.linalg.norm(rotated)
        if norm < 1e-9:
            continue
        best = max(best, _ccf_peak(a, rotated / norm))
    return best
