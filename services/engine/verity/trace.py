"""Per-land algorithmic trace — every intermediate the signature pipeline produces.

:func:`verity.signature.striation_signature` runs raw → form-removed → bandpassed
→ FFT-oriented → groove-cropped → 1-D signature and returns only the last step;
:func:`verity.region.extract_region` computes all the intermediates and discards
them. This module keeps them, in one :class:`LandTrace`, so the whole pipeline can
be *seen* (rendered to PNGs, stored in the catalog) and used to diagnose where
discrimination is won or lost on a given land.

The trace reuses the exact production transforms, so ``land_trace(...).signature``
is byte-identical to ``striation_signature(..., orient=True)`` — the trace cannot
drift from what the engine actually scores.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .preprocess import isolate_roughness, remove_form
from .region import DEFAULT_KEEP, extract_region
from .surface import Surface


@dataclass(frozen=True, eq=False)
class LandTrace:
    """The pipeline stages for one land. Arrays are 2-D heightmaps unless noted.

    * ``raw`` — heights as read (``dx``/``dy`` are the SI-metre pixel pitches)
    * ``bandpassed`` — after form removal + the ISO 16610 roughness band
    * ``rotated`` / ``rotated_mask`` — striae rotated vertical (``zr``, ``wr``)
    * ``profile_full`` — 1-D across-striae profile before the groove crop
    * ``crop`` — ``(lo, hi)`` kept column range (groove shoulders removed)
    * ``signature`` — 1-D ``profile_full[lo:hi]``; the comparison object
    * ``tilt_deg`` — rotation applied; ``striae_angle_deg`` — detected striae run
    """

    raw: np.ndarray
    dx: float
    dy: float
    bandpassed: np.ndarray
    rotated: np.ndarray
    rotated_mask: np.ndarray
    profile_full: np.ndarray
    crop: tuple[int, int]
    signature: np.ndarray
    tilt_deg: float
    striae_angle_deg: float


def land_trace(
    surface: Surface,
    *,
    lambda_s: float | None = None,
    lambda_c: float | None = None,
    degree: int = 2,
    keep: float = DEFAULT_KEEP,
) -> LandTrace:
    """Run the production signature pipeline, keeping every intermediate.

    Same arguments as :func:`verity.signature.striation_signature` (the
    ``orient=True`` path). ``signature`` is identical to that function's output."""
    s = remove_form(surface, degree=degree)
    if lambda_s is not None and lambda_c is not None:
        s = isolate_roughness(s, lambda_s, lambda_c)
    z = s.heights
    w = (~np.isnan(z)).astype(np.float64)
    zr, wr, prof, (lo, hi), tilt = extract_region(z, w, keep=keep)
    return LandTrace(
        raw=surface.heights,
        dx=surface.dx,
        dy=surface.dy,
        bandpassed=z,
        rotated=zr,
        rotated_mask=wr,
        profile_full=prof,
        crop=(lo, hi),
        signature=prof[lo:hi],
        tilt_deg=tilt,
        striae_angle_deg=90.0 - tilt,  # extract_region rotated by 90 - striae_angle
    )
