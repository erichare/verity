"""Congruent Matching Regions (CMR) — Congruent Matching Cells, generalized.

CMR lifts Song et al.'s Congruent Matching Cells (CMC, the cartridge-case method)
off of 2-D cells and fixed translation+rotation so the *same* algorithm scores any
mark. A **cell** becomes a **region** of any dimension; the fixed 2-D transform
becomes any transformation group:

    partition A into regions -> register each region against B over a group G ->
    count the regions whose best-fit transforms agree (the CMR count).

A genuine same-source pair has many regions that independently agree on one
geometry; a non-match's regions register at scattered offsets, so no large
congruent cluster forms. Only some regions need to match, which is why this is
robust to partial / damaged / warped marks where a single global cross-correlation
is brittle.

The core (:func:`cmr_count`) is domain-agnostic — it sees only ``(transform, corr)``
votes. Each modality supplies a **vote producer**: :func:`striated_votes` (1-D
windows + lag -> Chumbley / consecutive-matching-striae) and :func:`areal_votes`
(2-D cells + translation+rotation -> exactly CMC). See
``docs/congruent-matching-regions.md``.
"""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.ndimage import rotate
from skimage.feature import match_template

# --- domain-agnostic core ---------------------------------------------------

Vote = tuple[tuple[float, ...], float]  # (transform params, registration corr)

_DEFAULT_ANGLES = tuple(range(-30, 31, 5))  # rotation search grid (deg) for areal cells


def _congruent(t1: tuple[float, ...], t2: tuple[float, ...], tol: tuple[float, ...]) -> bool:
    return all(abs(a - b) <= d for a, b, d in zip(t1, t2, tol, strict=True))


def cmr_count(votes: list[Vote], *, corr_thresh: float, transform_tol: tuple[float, ...]) -> int:
    """The congruent-matching-region count: among well-registered regions
    (``corr >= corr_thresh``), the size of the largest cluster whose transforms
    all agree to within ``transform_tol``. This is the CMC count, generalized to
    arbitrary regions/transforms."""
    strong = [t for (t, c) in votes if c >= corr_thresh]
    if not strong:
        return 0
    best = 0
    for anchor in strong:  # greedy consensus: the most-agreed-upon transform
        best = max(best, sum(1 for t in strong if _congruent(t, anchor, transform_tol)))
    return best


# --- 1-D vote producer: striated marks (region = profile window, group = lag) ---


def _best_lag(segment: np.ndarray, target: np.ndarray, home: int) -> Vote:
    seg = segment - segment.mean()
    sn = np.linalg.norm(seg)
    if sn < 1e-9 or len(target) < len(seg):
        return ((0.0,), 0.0)
    windows = sliding_window_view(target, len(seg))
    wc = windows - windows.mean(axis=1, keepdims=True)
    wn = np.linalg.norm(wc, axis=1)
    ok = wn > 1e-9
    corr = np.full(len(windows), -1.0)
    corr[ok] = (wc[ok] @ seg) / (wn[ok] * sn)
    pos = int(np.argmax(corr))
    return ((float(pos - home),), float(corr[pos]))  # lag relative to the window's home


def striated_votes(a: np.ndarray, b: np.ndarray, *, window: int = 0, step: int = 0) -> list[Vote]:
    """Slide windows of profile ``a`` against ``b``; each votes its best lag. A
    same-source pair's windows share a common lag (the global alignment)."""
    window = window or max(16, len(a) // 6)
    step = step or max(1, window // 2)
    return [_best_lag(a[s : s + window], b, s) for s in range(0, len(a) - window + 1, step)]


# --- 2-D vote producer: impressed/areal marks (region = cell, group = shift+rot) ---


def _cell_vote(cell: np.ndarray, rotated_targets: dict, home_y: int, home_x: int) -> Vote:
    """Template-match a cell against B at each rotation; vote the best (dy, dx, θ)."""
    cy, cx = home_y + cell.shape[0] / 2.0, home_x + cell.shape[1] / 2.0
    best: Vote = ((0.0, 0.0, 0.0), -1.0)
    for theta, target in rotated_targets.items():
        res = match_template(target, cell, pad_input=True)
        peak = np.unravel_index(int(np.argmax(res)), res.shape)
        corr = float(res[peak])
        if corr > best[1]:
            best = ((float(peak[0] - cy), float(peak[1] - cx), float(theta)), corr)
    return best


def areal_votes(
    a: np.ndarray,
    b: np.ndarray,
    *,
    grid: int = 7,
    angles=_DEFAULT_ANGLES,
    min_energy: float = 1e-6,
) -> list[Vote]:
    """Divide ``a`` into a ``grid``x``grid`` of cells; each is registered against
    ``b`` over translation+rotation and votes its (dy, dx, θ). This is CMC."""
    gh, gw = a.shape[0] // grid, a.shape[1] // grid
    rotated = {
        float(t): (b if t == 0 else rotate(b, float(t), reshape=False, order=1)) for t in angles
    }
    votes: list[Vote] = []
    for gi in range(grid):
        for gj in range(grid):
            cell = a[gi * gh : (gi + 1) * gh, gj * gw : (gj + 1) * gw]
            if cell.size == 0 or float(np.sum(cell**2)) < min_energy:
                continue  # masked / empty region casts no vote
            votes.append(_cell_vote(cell, rotated, gi * gh, gj * gw))
    return votes


# --- convenience scorers ----------------------------------------------------


def cmr_score_1d(a, b, *, corr_thresh: float = 0.5, lag_tol: float = 10.0, **kw) -> int:
    """CMR for striated profiles (the 1-D / Chumbley instantiation)."""
    return cmr_count(striated_votes(a, b, **kw), corr_thresh=corr_thresh, transform_tol=(lag_tol,))


def cmr_score_2d(
    a, b, *, corr_thresh: float = 0.3, xy_tol: float = 20.0, theta_tol: float = 6.0, **kw
) -> int:
    """CMR for impressed/areal maps (the 2-D / CMC instantiation)."""
    return cmr_count(
        areal_votes(a, b, **kw), corr_thresh=corr_thresh, transform_tol=(xy_tol, xy_tol, theta_tol)
    )
