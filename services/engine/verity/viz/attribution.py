"""Render the matched-region attribution overlay (server-side).

The web UI draws the congruent regions over the surface previews client-side; the
court-ready PDF needs the same overlay rendered on the server. Both consume the
same fractional region coordinates from the comparison report, so the PDF figure
and the on-screen figure agree.
"""

from __future__ import annotations

import numpy as np


def render_attribution_axes(ax, preview, regions, *, title: str = "") -> None:
    """Draw a grayscale preview grid with the matched regions outlined.

    ``preview`` is the downsampled [0,1] height grid from the report; ``regions``
    are the report's attribution entries with fractional ``x_frac``/``y_frac``/
    ``w_frac``/``h_frac`` coordinates."""
    from matplotlib.patches import Rectangle

    grid = np.asarray(preview, dtype=float)
    if grid.ndim != 2 or grid.size == 0:
        ax.text(0.5, 0.5, "no preview", ha="center", va="center", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(title, fontsize=9)
        return
    ny, nx = grid.shape
    ax.imshow(grid, cmap="gray", aspect="auto", vmin=0.0, vmax=1.0)
    for r in regions:
        x = float(r.get("x_frac", 0.0)) * nx
        y = float(r.get("y_frac", 0.0)) * ny
        w = float(r.get("w_frac", 0.0)) * nx
        h = float(r.get("h_frac", 0.0)) * ny
        ax.add_patch(
            Rectangle((x, y), w, h, fill=False, edgecolor="#f1c40f", linewidth=1.5, alpha=0.9)
        )
    ax.set_title(title, fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])
