"""Dominant-texture orientation via the structure tensor — the front-end that
lets striated marks be normalized to a canonical (vertical-striae) frame, so a
1-D and a 2-D mark flow through one pipeline."""

from __future__ import annotations

import numpy as np
from scipy.ndimage import gaussian_filter

from .surface import Surface


def dominant_orientation(surface: Surface, smoothing: float = 3.0) -> float:
    """Angle (radians, in ``[0, π)``) of the dominant texture direction — the
    direction along which the surface varies *least* (the direction striae run).

    Computed from the structure tensor: the dominant gradient direction is the
    eigenvector of the largest eigenvalue; the texture runs perpendicular to it.
    """
    z = np.nan_to_num(surface.heights - np.nanmean(surface.heights))
    gy, gx = np.gradient(z)
    jxx = float(gaussian_filter(gx * gx, smoothing).sum())
    jyy = float(gaussian_filter(gy * gy, smoothing).sum())
    jxy = float(gaussian_filter(gx * gy, smoothing).sum())

    gradient_angle = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    return float((gradient_angle + np.pi / 2.0) % np.pi)
