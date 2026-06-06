"""Render a bullet-pair comparison to a PNG: CCF matrix, overlays, features."""

from __future__ import annotations

import numpy as np

from ..aggregate import BulletComparison


def _z(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    return (x - np.nanmean(x)) / (np.nanstd(x) + 1e-9)


def render_pair_trace(
    cmp: BulletComparison,
    sigs_a: list[np.ndarray],
    sigs_b: list[np.ndarray],
    out_path: str,
    title: str = "",
    label: int | None = None,
) -> None:
    """Draw the land×land CCF matrix (matched diagonal boxed), the matched-land
    signature overlays (B shifted to A by the per-land lag), and the structure
    features. The diagnostic for *why* a comparison scored as it did — a flat
    matrix with a lucky cell is a KNM near-miss; a faint diagonal a KM that the
    mean score under-weights."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n, mm = cmp.ccf.shape
    fig = plt.figure(figsize=(13, 6))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.0, 1.2])

    ax = fig.add_subplot(gs[:, 0])
    im = ax.imshow(cmp.ccf, cmap="viridis", aspect="auto", vmin=-0.2, vmax=1.0)
    for i in range(n):
        j = (i + cmp.offset) % mm
        ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor="red", lw=1.8))
    ax.set_title(f"land×land CCF (best offset {cmp.offset}, red = matched diagonal)", fontsize=9)
    ax.set_xlabel("bullet B land")
    ax.set_ylabel("bullet A land")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = fig.add_subplot(gs[0, 1])
    for i in range(n):
        j = (i + cmp.offset) % mm
        a = _z(sigs_a[i])
        b = _z(np.roll(sigs_b[j], int(cmp.diag_lags[i])))
        length = min(a.size, b.size)
        ax.plot(np.arange(length), a[:length] + i * 4.0, color="C0", lw=0.7)
        ax.plot(np.arange(length), b[:length] + i * 4.0, color="C3", lw=0.7, alpha=0.8)
    ax.set_title("matched-land overlays (blue = A, red = B shifted by lag)", fontsize=9)
    ax.set_yticks([])

    ax = fig.add_subplot(gs[1, 1])
    ax.axis("off")
    lines = [f"{k:>14s} : {v:+.3f}" for k, v in cmp.features().items()]
    if label is not None:
        lines.insert(0, f"{'label':>14s} : {'KM' if label else 'KNM'}")
    ax.text(0.02, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=10)

    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
