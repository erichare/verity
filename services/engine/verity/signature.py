"""Striation signature extraction for striated marks (bullet lands).

Turns a 2-D land surface into the 1-D striation profile that is the comparison
object: remove form, isolate the roughness band, rotate so striae run
vertically, then average *along* the striae.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import rotate

from .orientation import dominant_orientation
from .preprocess import isolate_roughness, remove_form
from .surface import Surface


def striation_signature(
    surface: Surface,
    *,
    lambda_s: float | None = None,
    lambda_c: float | None = None,
    degree: int = 2,
    orient: bool = True,
) -> np.ndarray:
    """Extract the 1-D striation signature.

    With ``lambda_s``/``lambda_c`` set, the surface is bandpassed to the
    individualizing roughness band first. When ``orient`` is true the striae are
    rotated to vertical (via :func:`dominant_orientation`) before collapsing, so
    the signature is orientation-invariant. Returns a 1-D array (the profile
    across the land); collapsed columns with no valid data are ``NaN``.
    """
    s = remove_form(surface, degree=degree)
    if lambda_s is not None and lambda_c is not None:
        s = isolate_roughness(s, lambda_s, lambda_c)
    z = s.heights

    if orient:
        angle = dominant_orientation(s)
        rot_deg = float(np.degrees(np.pi / 2.0 - angle))
        filled = np.nan_to_num(z)
        weight = (~np.isnan(z)).astype(np.float64)
        z_rot = rotate(filled, rot_deg, reshape=False, order=1, cval=0.0)
        w_rot = rotate(weight, rot_deg, reshape=False, order=1, cval=0.0)
        num = z_rot.sum(axis=0)
        den = w_rot.sum(axis=0)
        return np.where(den > 1e-9, num / den, np.nan)

    return np.nanmean(z, axis=0)
