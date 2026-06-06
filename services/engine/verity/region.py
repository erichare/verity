"""Stage-0 region extraction for striated marks.

A bullet land (or any striated mark) carries individualizing signal only in part
of the scan: the groove shoulders at the two ends of the across-striae axis are
~25x the amplitude of the striae and are common to every land, so they swamp the
cross-correlation; the striae themselves occupy only the inner ~40-60%. This
module isolates that band:

1. **Orient** the striae vertical via the 2-D power spectrum — striae are parallel
   lines whose energy concentrates *across* them in the FFT, and the
   low-frequency grooves and the rectangular-edge cross are excluded, so it is
   robust where a structure-tensor or variance search is fooled (wide scans).
2. **Collapse** along the striae to the across-striae profile.
3. **Crop** a fixed fraction off each end to remove both groove shoulders,
   keeping the inner striae band.

Replacing the structure-tensor orientation with this on the real data took the
barrel-disjoint ``Cllr`` from 0.60 to 0.11 on Hamby-252 and recovered the
wide-scan studies (Phoenix/Hamby-173) from chance to AUC ~0.96.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import rotate

DEFAULT_KEEP = 0.5


def striae_angle(z: np.ndarray, w: np.ndarray) -> float:
    """Direction (deg) the striae run, from the 2-D power spectrum. A Hann window
    suppresses the rectangular-edge cross and a mid-frequency band drops the DC
    term and the low-frequency grooves, leaving the striae periodicity."""
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
    band = (r > 0.04 * rmax) & (r < 0.5 * rmax)
    pm = power * band
    total = pm.sum() + 1e-12
    ixx = (pm * xx * xx).sum() / total
    iyy = (pm * yy * yy).sum() / total
    ixy = (pm * xx * yy).sum() / total
    across = 0.5 * np.degrees(np.arctan2(2.0 * ixy, ixx - iyy))  # dominant power dir
    return across + 90.0  # striae run perpendicular to the dominant frequency


def _collapse(z: np.ndarray, w: np.ndarray, axis: int) -> np.ndarray:
    num = (z * w).sum(axis)
    den = w.sum(axis)
    out = np.full(den.shape, np.nan)
    np.divide(num, den, out=out, where=den > 1e-9)  # skip empty columns, no warning
    return out


def oriented_field(z: np.ndarray, w: np.ndarray):
    """Rotate so the striae are vertical (long axis horizontal) and crop to the
    full-validity interior. Returns ``(zr, wr, tilt_deg)``."""
    tilt = 90.0 - striae_angle(z, w)
    zr = rotate(np.nan_to_num(z), tilt, reshape=True, order=1, cval=0.0)
    wr = rotate(w, tilt, reshape=True, order=1, cval=0.0)
    rows = np.where(wr.mean(1) > 0.85)[0]
    cols = np.where(wr.mean(0) > 0.85)[0]
    if len(rows) and len(cols):
        zr = zr[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
        wr = wr[rows[0] : rows[-1] + 1, cols[0] : cols[-1] + 1]
    return zr, wr, tilt


def extract_region(z: np.ndarray, w: np.ndarray, *, keep: float = DEFAULT_KEEP):
    """Full Stage-0 extraction. Returns ``(zr, wr, profile, (lo, hi), tilt)`` —
    the oriented field, its validity, the across-striae profile, the kept column
    range (grooves cropped), and the rotation applied."""
    zr, wr, tilt = oriented_field(z, w)
    prof = _collapse(zr, wr, axis=0)
    m = int((1.0 - keep) / 2.0 * len(prof))
    lo, hi = (m, len(prof) - m) if len(prof) - 2 * m > 10 else (0, len(prof))
    return zr, wr, prof, (lo, hi), tilt


def region_signature(z: np.ndarray, w: np.ndarray, *, keep: float = DEFAULT_KEEP) -> np.ndarray:
    """The groove-cropped across-striae signature (the comparison object)."""
    _, _, prof, (lo, hi), _ = extract_region(z, w, keep=keep)
    return prof[lo:hi]
