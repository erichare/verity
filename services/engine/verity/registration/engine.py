"""The ``register(source, target, group)`` dispatcher.

One entry point over a hierarchy of transformation groups, so a new forensic
modality just declares which group its marks live in:

* ``translation_1d`` — striated marks (bullet lands, striated toolmarks): collapse
  to a profile and 1-D cross-correlate.
* ``translation_2d`` — areal/impressed marks (breech-face, footwear): 2-D phase
  correlation.
* ``rigid_2d`` — adds rotation; arrives with the method layer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..surface import Surface
from .align import align_1d, ncc_at_shift


@dataclass(frozen=True)
class Registration:
    """The estimated alignment of ``target`` onto ``source``."""

    group: str
    shift: tuple[float, ...]
    score: float  # similarity at the recovered alignment, in [-1, 1]


def register(source: Surface, target: Surface, group: str = "translation_2d") -> Registration:
    if group == "translation_1d":
        a = np.nanmean(source.heights, axis=0)
        b = np.nanmean(target.heights, axis=0)
        lag, ccf = align_1d(a, b)
        return Registration(group, (float(lag),), ccf)

    if group == "translation_2d":
        from skimage.registration import phase_cross_correlation

        a = np.nan_to_num(source.heights - np.nanmean(source.heights))
        b = np.nan_to_num(target.heights - np.nanmean(target.heights))
        shift, _, _ = phase_cross_correlation(a, b, normalization=None)
        dy, dx = int(round(shift[0])), int(round(shift[1]))
        score = ncc_at_shift(a, b, dy, dx)
        return Registration(group, (float(shift[0]), float(shift[1])), score)

    if group == "rigid_2d":
        raise NotImplementedError("rigid_2d (rotation) registration arrives with the method layer")

    raise ValueError(f"unknown registration group: {group!r}")
