"""The in-memory surface the engine operates on."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Surface:
    """A 2.5-D areal surface: a height field with a pixel pitch.

    ``heights`` is a ``(ny, nx)`` float64 array; invalid/unmeasured points are
    ``NaN`` (matching the X3P codec). ``dx``/``dy`` are the sample spacings along
    X and Y, in the same length unit as the heights (X3P is SI metres).
    Immutable — every transform returns a new ``Surface``.
    """

    heights: np.ndarray
    dx: float
    dy: float

    def __post_init__(self) -> None:
        if self.heights.ndim != 2:
            raise ValueError(f"heights must be 2-D, got shape {self.heights.shape}")

    @property
    def mask(self) -> np.ndarray:
        """Boolean validity mask (``True`` = measured)."""
        return ~np.isnan(self.heights)

    @property
    def shape(self) -> tuple[int, int]:
        return self.heights.shape  # type: ignore[return-value]

    @property
    def ny(self) -> int:
        return self.heights.shape[0]

    @property
    def nx(self) -> int:
        return self.heights.shape[1]

    def with_heights(self, heights: np.ndarray) -> Surface:
        """A copy with new heights (same pitch)."""
        return Surface(heights=heights, dx=self.dx, dy=self.dy)
