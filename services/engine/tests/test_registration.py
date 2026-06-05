import numpy as np
import pytest
from scipy.ndimage import gaussian_filter

from verity import Surface, align_1d, register


def test_align_1d_recovers_shift_and_correlation():
    x = np.arange(500)
    a = np.sin(2 * np.pi * x / 13.0) + 0.5 * np.sin(2 * np.pi * x / 7.0)
    b = np.roll(a, 9)
    lag, ccf = align_1d(a, b)
    # circular roll vs linear correlation overlaps N-|lag| samples, so a perfect
    # shift scores just under 1; the lag is exact.
    assert ccf > 0.95
    assert abs(abs(lag) - 9) <= 1


def test_register_translation_1d():
    nx = 400
    x = np.arange(nx)
    profile = np.sin(2 * np.pi * x / 15.0)
    a = Surface(heights=np.tile(profile, (20, 1)), dx=1.0, dy=1.0)
    b = Surface(heights=np.tile(np.roll(profile, 12), (20, 1)), dx=1.0, dy=1.0)

    reg = register(a, b, group="translation_1d")

    assert reg.group == "translation_1d"
    assert reg.score > 0.95


def test_register_translation_2d_recovers_shift():
    rng = np.random.default_rng(0)
    base = gaussian_filter(rng.standard_normal((64, 64)), 1.5)
    a = Surface(heights=base.copy(), dx=1.0, dy=1.0)
    b = Surface(heights=np.roll(np.roll(base, 5, axis=0), -3, axis=1), dx=1.0, dy=1.0)

    reg = register(a, b, group="translation_2d")

    dy, dx = reg.shift
    assert reg.score > 0.95
    assert {abs(round(dy)), abs(round(dx))} == {3, 5}


def test_rigid_2d_not_implemented():
    a = Surface(heights=np.zeros((8, 8)), dx=1.0, dy=1.0)
    with pytest.raises(NotImplementedError):
        register(a, a, group="rigid_2d")


def test_unknown_group_raises():
    a = Surface(heights=np.zeros((8, 8)), dx=1.0, dy=1.0)
    with pytest.raises(ValueError, match="unknown registration group"):
        register(a, a, group="affine")
