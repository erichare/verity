"""Render a :class:`verity.trace.LandTrace` to a four-panel PNG."""

from __future__ import annotations

import numpy as np

from ..trace import LandTrace


def _heatmap(ax, data: np.ndarray, title: str) -> None:
    disp = np.where(np.isfinite(data), data, np.nan)
    vals = disp[np.isfinite(disp)]
    vmin, vmax = (np.percentile(vals, [2, 98]) if vals.size else (-1.0, 1.0))
    ax.imshow(disp, cmap="gray", vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_title(title, fontsize=9)
    ax.set_xticks([])
    ax.set_yticks([])


def render_land_trace(trace: LandTrace, out_path: str, title: str = "") -> None:
    """Draw raw → bandpassed → oriented+cropped → signature for one land.

    Panel 3 marks the kept striae band (yellow) and the dropped groove shoulders
    (red); panel 4 shows the full across-striae profile with the signature slice
    highlighted. Reveals at a glance a bad rotation, grooves leaking past the
    crop, or a damaged land."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    _heatmap(axes[0, 0], trace.raw, "1. raw surface")
    _heatmap(axes[0, 1], trace.bandpassed, "2. bandpassed (roughness band)")

    ax = axes[1, 0]
    disp = np.where(trace.rotated_mask > 0.5, trace.rotated, np.nan)
    vals = disp[np.isfinite(disp)]
    vmin, vmax = (np.percentile(vals, [2, 98]) if vals.size else (-1.0, 1.0))
    h, width = disp.shape
    ax.imshow(disp, cmap="gray", vmin=vmin, vmax=vmax, aspect="auto", extent=[0, width, h, 0])
    lo, hi = trace.crop
    ax.axvspan(0, lo, color="red", alpha=0.22)
    ax.axvspan(hi, width, color="red", alpha=0.22)
    ax.add_patch(plt.Rectangle((lo, 0), hi - lo, h, fill=False, edgecolor="yellow", lw=2.0))
    ax.set_title(
        f"3. striae vertical (tilt {trace.tilt_deg:+.0f}°)  yellow = kept  red = grooves",
        fontsize=9,
    )
    ax.set_xticks([])
    ax.set_yticks([])

    ax = axes[1, 1]
    prof = trace.profile_full
    ax.plot(np.arange(prof.size), prof, color="0.65", lw=0.8, label="full profile")
    ax.axvspan(0, lo, color="red", alpha=0.12)
    ax.axvspan(hi, prof.size, color="red", alpha=0.12)
    ax.plot(np.arange(lo, hi), prof[lo:hi], color="C0", lw=1.2, label="signature")
    ax.set_title("4. across-striae profile → signature", fontsize=9)
    ax.set_xlabel("across-striae (px)", fontsize=8)
    ax.legend(fontsize=7, loc="upper right")

    fig.suptitle(title, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
