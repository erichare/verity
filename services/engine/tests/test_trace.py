"""Tests for the per-land algorithmic trace.

The load-bearing guarantee: the trace's signature is byte-identical to what the
engine actually scores, so a trace never misrepresents the pipeline.
"""

import numpy as np

from verity import Surface, striation_signature
from verity.trace import land_trace


def _striae_surface(nx=200, ny=120, wavelength=12.0, seed=0):
    rng = np.random.default_rng(seed)
    x = np.arange(nx)
    profile = np.sin(2 * np.pi * x / wavelength) + 0.4 * np.sin(2 * np.pi * x / 5.0)
    z = np.tile(profile, (ny, 1)) + 0.05 * rng.standard_normal((ny, nx))
    return Surface(heights=z, dx=1.0, dy=1.0)


def test_trace_signature_identical_to_production_bandpassed():
    s = _striae_surface()
    tr = land_trace(s, lambda_s=4.0, lambda_c=80.0)
    sig = striation_signature(s, lambda_s=4.0, lambda_c=80.0, orient=True)
    assert np.array_equal(tr.signature, sig)


def test_trace_signature_identical_to_production_no_bandpass():
    s = _striae_surface()
    tr = land_trace(s)
    sig = striation_signature(s, orient=True)
    assert np.array_equal(tr.signature, sig)


def test_trace_fields_are_consistent():
    s = _striae_surface()
    tr = land_trace(s, lambda_s=4.0, lambda_c=80.0)
    lo, hi = tr.crop
    assert tr.raw.ndim == 2
    assert tr.rotated.ndim == 2
    assert tr.signature.ndim == 1
    assert 0 <= lo < hi <= tr.profile_full.size
    assert np.array_equal(tr.signature, tr.profile_full[lo:hi])
    assert tr.rotated.shape == tr.rotated_mask.shape
    assert abs(tr.striae_angle_deg - (90.0 - tr.tilt_deg)) < 1e-9
