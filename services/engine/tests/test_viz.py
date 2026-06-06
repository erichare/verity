"""Smoke tests for the trace renderers (skipped if matplotlib is absent)."""

import numpy as np
import pytest

from verity import Surface
from verity.aggregate import bullet_comparison
from verity.trace import land_trace


def test_render_land_trace_writes_png(tmp_path):
    pytest.importorskip("matplotlib")
    from verity.viz import render_land_trace

    rng = np.random.default_rng(0)
    x = np.arange(200)
    z = np.tile(np.sin(2 * np.pi * x / 12.0), (120, 1)) + 0.05 * rng.standard_normal((120, 200))
    tr = land_trace(Surface(heights=z, dx=1.0, dy=1.0), lambda_s=4.0, lambda_c=80.0)
    out = tmp_path / "land.png"
    render_land_trace(tr, str(out), title="test land")
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_pair_trace_writes_png(tmp_path):
    pytest.importorskip("matplotlib")
    from verity.viz import render_pair_trace

    rng = np.random.default_rng(1)
    sigs_a = [rng.standard_normal(120) for _ in range(6)]
    sigs_b = [s + 0.1 * rng.standard_normal(120) for s in sigs_a]
    cmp = bullet_comparison(sigs_a, sigs_b)
    out = tmp_path / "pair.png"
    render_pair_trace(cmp, sigs_a, sigs_b, str(out), title="test pair", label=1)
    assert out.exists()
    assert out.stat().st_size > 0
