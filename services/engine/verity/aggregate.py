"""Bullet-to-bullet aggregation of land-level cross-correlations.

A bullet carries several lands; comparing two bullets means comparing every land
of one against every land of the other, then reading the structure of the
resulting matrix. Genuine same-source (KM) bullets line up on a single cyclic
diagonal — one land offset makes *all* land pairs correlate, at *consistent*
lags. Different-source (KNM) bullets have no such diagonal; a high mean there is
the luck of the maximum over offsets.

The Phase-1 score collapses this to one number — the best mean diagonal CCF (the
bulletxtrctr "average of the diagonal"). That throws away exactly the structure
that separates a real match from a lucky one: how far the matched diagonal stands
*above* the rest of the matrix, how far the winning offset beats the runner-up,
whether the per-land lags agree. This module computes the full matrix once and
exposes both the scalar score (unchanged) and those discarded structure features,
so the validation harness can test whether they widen the KM/KNM margin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .registration import align_1d


def land_ccf_matrix(
    sigs_a: list[np.ndarray], sigs_b: list[np.ndarray]
) -> tuple[np.ndarray, np.ndarray]:
    """Land-to-land normalized cross-correlation and integer lag for every pair.

    Returns ``(ccf, lags)``, each shaped ``(len(sigs_a), len(sigs_b))``: ``ccf[i,
    j]`` is the peak normalized cross-correlation of land ``i`` of bullet A with
    land ``j`` of bullet B, and ``lags[i, j]`` the shift that achieves it."""
    n, mm = len(sigs_a), len(sigs_b)
    ccf = np.empty((n, mm), dtype=np.float64)
    lags = np.empty((n, mm), dtype=np.float64)
    for i, a in enumerate(sigs_a):
        for j, b in enumerate(sigs_b):
            lag, c = align_1d(a, b)
            ccf[i, j] = c
            lags[i, j] = lag
    return ccf, lags


def diagonal_means(ccf: np.ndarray) -> np.ndarray:
    """Mean CCF along each cyclic land offset ``k``:
    ``out[k] = mean_i ccf[i, (i + k) % mm]``. Length ``mm``."""
    n, mm = ccf.shape
    return np.array([np.mean([ccf[i, (i + k) % mm] for i in range(n)]) for k in range(mm)])


def best_diagonal(ccf: np.ndarray) -> tuple[int, np.ndarray]:
    """The cyclic land offset maximizing the mean diagonal CCF. Returns
    ``(offset, diag)`` where ``diag[i] = ccf[i, (i + offset) % mm]``."""
    n, mm = ccf.shape
    offset = int(np.argmax(diagonal_means(ccf)))
    diag = np.array([ccf[i, (i + offset) % mm] for i in range(n)])
    return offset, diag


@dataclass(frozen=True, eq=False)
class BulletComparison:
    """Everything one bullet-pair comparison computed: the full land×land CCF and
    lag matrices, the winning cyclic offset, and the CCF/lag along that diagonal.
    Features (all oriented so *higher = more KM-like*) are derived properties."""

    ccf: np.ndarray  # (n, mm) land-to-land CCF
    lags: np.ndarray  # (n, mm) integer lags
    offset: int  # winning cyclic land offset
    diag_ccf: np.ndarray  # (n,) CCF along the best diagonal
    diag_lags: np.ndarray  # (n,) lags along the best diagonal

    @property
    def diag_mean(self) -> float:
        """Mean CCF along the best diagonal — the Phase-1 bullet score."""
        return float(np.mean(self.diag_ccf))

    @property
    def diag_min(self) -> float:
        """Weakest land match along the diagonal. A real bullet matches on *all*
        lands; a lucky KNM mean is usually carried by one or two."""
        return float(np.min(self.diag_ccf))

    @property
    def off_diag_mean(self) -> float:
        """Mean CCF of all entries *not* on the best diagonal — the background
        correlation level for this comparison."""
        n, mm = self.ccf.shape
        mask = np.ones((n, mm), dtype=bool)
        for i in range(n):
            mask[i, (i + self.offset) % mm] = False
        return float(self.ccf[mask].mean()) if mask.any() else 0.0

    @property
    def diag_contrast(self) -> float:
        """How far the matched diagonal stands above the rest of the matrix. Near
        zero for KNM (no special diagonal), large for KM."""
        return self.diag_mean - self.off_diag_mean

    @property
    def offset_margin(self) -> float:
        """Best diagonal mean minus the runner-up offset's mean. KM: one rotation
        dominates; KNM: all offsets are interchangeable noise (~0)."""
        means = np.sort(diagonal_means(self.ccf))[::-1]
        return float(means[0] - means[1]) if means.size > 1 else float(means[0])

    @property
    def lag_coherence(self) -> float:
        """``1 / (1 + std(diag_lags))`` in ``(0, 1]``. KM land pairs align at a
        consistent relative shift (coherent lags → high); KNM lags scatter."""
        return float(1.0 / (1.0 + np.std(self.diag_lags)))

    def features(self) -> dict[str, float]:
        """All structure features as a dict (higher = more KM-like)."""
        return {
            "diag_mean": self.diag_mean,
            "diag_min": self.diag_min,
            "diag_contrast": self.diag_contrast,
            "offset_margin": self.offset_margin,
            "lag_coherence": self.lag_coherence,
        }


def bullet_comparison(
    sigs_a: list[np.ndarray], sigs_b: list[np.ndarray]
) -> BulletComparison | None:
    """Compare two bullets' land signatures. ``None`` if either has no lands."""
    if not sigs_a or not sigs_b:
        return None
    ccf, lags = land_ccf_matrix(sigs_a, sigs_b)
    offset, diag = best_diagonal(ccf)
    mm = ccf.shape[1]
    diag_lags = np.array([lags[i, (i + offset) % mm] for i in range(len(sigs_a))])
    return BulletComparison(ccf=ccf, lags=lags, offset=offset, diag_ccf=diag, diag_lags=diag_lags)


def bullet_score(sigs_a: list[np.ndarray], sigs_b: list[np.ndarray]) -> float:
    """Best mean land-to-land CCF over cyclic land rotations — the Phase-1 score.
    Thin wrapper over :func:`bullet_comparison` (identical to the original)."""
    cmp = bullet_comparison(sigs_a, sigs_b)
    return float("nan") if cmp is None else cmp.diag_mean
