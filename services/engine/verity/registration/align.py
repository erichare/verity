"""Low-level alignment primitives."""

from __future__ import annotations

import numpy as np
from scipy.signal import correlate


def align_1d(a: np.ndarray, b: np.ndarray) -> tuple[int, float]:
    """Best integer-lag normalized cross-correlation of two 1-D signals.

    Returns ``(lag, ccf)`` where ``ccf`` in ``[-1, 1]`` is the maximum normalized
    cross-correlation and ``lag`` is the shift of ``b`` relative to ``a`` that
    achieves it. NaNs are treated as zero after mean-centering.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    a = np.nan_to_num(a - np.nanmean(a))
    b = np.nan_to_num(b - np.nanmean(b))

    norm_a = np.sqrt(np.sum(a * a))
    norm_b = np.sqrt(np.sum(b * b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0, 0.0

    corr = correlate(a, b, mode="full") / (norm_a * norm_b)
    lags = np.arange(-(len(b) - 1), len(a))
    best = int(np.argmax(corr))
    return int(lags[best]), float(corr[best])


def ncc_at_shift(a: np.ndarray, b: np.ndarray, dy: int, dx: int) -> float:
    """Normalized cross-correlation of ``a`` and ``b`` after shifting ``b`` by
    ``(dy, dx)`` (circular). NaNs are zeroed after mean-centering."""
    a = np.nan_to_num(np.asarray(a, np.float64) - np.nanmean(a))
    shifted = np.roll(np.roll(np.asarray(b, np.float64), dy, axis=0), dx, axis=1)
    shifted = np.nan_to_num(shifted - np.nanmean(shifted))
    denom = np.sqrt(np.sum(a * a) * np.sum(shifted * shifted))
    return float(np.sum(a * shifted) / denom) if denom > 0 else 0.0
