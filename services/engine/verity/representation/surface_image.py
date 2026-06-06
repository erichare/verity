"""Turn a 2-D land surface into a fixed-size, orientation-normalized image — the
Phase-2 representation that the learned encoder consumes.

The Phase-2b encoder embedded the *collapsed 1-D signature*, throwing away all
cross-striation structure. Here we keep the 2-D oriented roughness field: reuse
the same Phase-1 metrology (form removal + ISO 16610 bandpass + dominant
orientation), rotate so striae run vertically, crop to the measured region, and
resample to a fixed square grid. Output is a 2-channel ``(2, size, size)`` tensor
— channel 0 the normalized height, channel 1 the validity mask — so the network
sees physical roughness *and* where data is missing.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import rotate
from skimage.transform import resize

from ..orientation import dominant_orientation
from ..preprocess import isolate_roughness, remove_form
from ..surface import Surface

DEFAULT_SIZE = 64


def _crop_to_valid(z: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Crop both arrays to the bounding box of ``w > 0.5`` (drops rotation padding)."""
    valid = w > 0.5
    if not valid.any():
        return z, w
    rows = np.where(valid.any(axis=1))[0]
    cols = np.where(valid.any(axis=0))[0]
    sl = (slice(rows[0], rows[-1] + 1), slice(cols[0], cols[-1] + 1))
    return z[sl], w[sl]


def land_image(
    surface: Surface,
    *,
    lambda_s: float | None = None,
    lambda_c: float | None = None,
    degree: int = 2,
    size: int = DEFAULT_SIZE,
    orient: bool = True,
) -> np.ndarray:
    """A ``(2, size, size)`` float32 tensor: [normalized height, validity mask].

    Mirrors :func:`verity.striation_signature` up to the collapse step, then keeps
    the 2-D field instead of averaging along the striae."""
    s = remove_form(surface, degree=degree)
    if lambda_s is not None and lambda_c is not None:
        s = isolate_roughness(s, lambda_s, lambda_c)
    z = s.heights
    w = (~np.isnan(z)).astype(np.float64)
    filled = np.nan_to_num(z)

    if orient:
        rot_deg = float(np.degrees(np.pi / 2.0 - dominant_orientation(s)))
        filled = rotate(filled, rot_deg, reshape=True, order=1, cval=0.0)
        w = rotate(w, rot_deg, reshape=True, order=1, cval=0.0)

    filled, w = _crop_to_valid(filled, w)

    z_grid = resize(filled, (size, size), order=1, mode="edge", anti_aliasing=False)
    m_grid = resize(w, (size, size), order=1, mode="edge", anti_aliasing=False)
    mask = (m_grid > 0.5).astype(np.float32)

    vals = z_grid[mask > 0]
    if vals.size > 1 and vals.std() > 0:
        z_grid = (z_grid - vals.mean()) / vals.std()
    z_grid = (z_grid * mask).astype(np.float32)
    return np.stack([z_grid, mask])
