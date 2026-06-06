"""Striation signature extraction for striated marks (bullet lands).

Turns a 2-D land surface into the 1-D striation profile that is the comparison
object: remove form, isolate the roughness band, then (when ``orient``) run the
Stage-0 region extraction — FFT-orient the striae vertical, collapse along them,
and crop the groove shoulders — leaving the across-striae striae signature. See
:mod:`verity.region`.
"""

from __future__ import annotations

import numpy as np

from .preprocess import isolate_roughness, remove_form
from .region import DEFAULT_KEEP, region_signature
from .surface import Surface


def striation_signature(
    surface: Surface,
    *,
    lambda_s: float | None = None,
    lambda_c: float | None = None,
    degree: int = 2,
    orient: bool = True,
    keep: float = DEFAULT_KEEP,
) -> np.ndarray:
    """Extract the 1-D striation signature.

    With ``lambda_s``/``lambda_c`` set, the surface is bandpassed to the
    individualizing roughness band first. When ``orient`` is true the Stage-0
    region extraction (:func:`verity.region.region_signature`) FFT-orients the
    striae vertical, collapses along them, and crops the groove shoulders to the
    inner ``keep`` fraction. With ``orient`` false the rows are simply averaged
    (assumes vertical striae, no cropping). Returns a 1-D array."""
    s = remove_form(surface, degree=degree)
    if lambda_s is not None and lambda_c is not None:
        s = isolate_roughness(s, lambda_s, lambda_c)
    z = s.heights

    if orient:
        w = (~np.isnan(z)).astype(np.float64)
        return region_signature(z, w, keep=keep)

    return np.nanmean(z, axis=0)
