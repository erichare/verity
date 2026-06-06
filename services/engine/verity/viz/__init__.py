"""Rendering of algorithmic traces to PNG artifacts.

``render_land_trace`` draws the per-land pipeline (raw → bandpassed → oriented +
cropped → signature); ``render_pair_trace`` draws a bullet-pair comparison (the
land×land CCF matrix, matched-land overlays, and the structure features). Both
make the pipeline auditable and drive the diagnosis of where the KM/KNM margin is
won or lost. matplotlib is imported lazily so the engine has no hard dependency on
it — install the ``viz`` extra or run with ``uv run --with matplotlib``.
"""

from .land_trace import render_land_trace
from .pair_trace import render_pair_trace

__all__ = ["render_land_trace", "render_pair_trace"]
