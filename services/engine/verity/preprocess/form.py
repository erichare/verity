"""Form removal (the ISO 25178 F-operation): subtract a least-squares
polynomial so that only the texture remains."""

from __future__ import annotations

import numpy as np

from ..surface import Surface


def _poly_terms(xn: np.ndarray, yn: np.ndarray, degree: int) -> list[np.ndarray]:
    """Monomials ``xn**i * yn**j`` with total degree ``i + j <= degree``."""
    terms = []
    for i in range(degree + 1):
        for j in range(degree + 1 - i):
            terms.append(xn**i * yn**j)
    return terms


def remove_form(surface: Surface, degree: int = 2) -> Surface:
    """Subtract a least-squares 2-D polynomial of total ``degree`` (the
    F-operation), fitting only the valid points. Removes gross shape such as the
    curvature of a bullet land, leaving waviness + roughness. Invalid points
    stay ``NaN``.
    """
    z = surface.heights
    ny, nx = z.shape
    yy, xx = np.mgrid[0:ny, 0:nx].astype(np.float64)
    # Normalise coordinates to [-1, 1] for a well-conditioned fit.
    xn = xx / max(nx - 1, 1) * 2.0 - 1.0
    yn = yy / max(ny - 1, 1) * 2.0 - 1.0

    mask = ~np.isnan(z)
    terms = _poly_terms(xn, yn, degree)
    design = np.stack([t[mask] for t in terms], axis=1)
    coef, *_ = np.linalg.lstsq(design, z[mask], rcond=None)

    fit = np.zeros_like(z)
    for c, t in zip(coef, terms, strict=True):
        fit += c * t

    out = z - fit
    out[~mask] = np.nan
    return surface.with_heights(out)
