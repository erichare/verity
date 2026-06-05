"""Smoke tests for the verity_x3p Python binding.

Run directly (``python tests/test_smoke.py``) or under pytest.
"""

import tempfile
from pathlib import Path

import numpy as np

import verity_x3p

FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "csafe-logo.x3p"


def test_read_real_fixture():
    s = verity_x3p.read_x3p(str(FIXTURE))
    assert (s.ny, s.nx) == (419, 741)
    assert s.data.shape == (419, 741)
    assert s.data.dtype == np.float64
    assert s.mask.shape == (419, 741)
    assert s.mask.dtype == np.bool_
    assert s.z_type == "D"
    assert s.mask.sum() > 0
    # Every invalid point is NaN.
    assert np.isnan(s.data[~s.mask]).all()


def test_roundtrip_file():
    s = verity_x3p.read_x3p(str(FIXTURE))
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "copy.x3p")
        verity_x3p.write_x3p(s, p, z_type="D")
        back = verity_x3p.read_x3p(p)
    assert back.data.shape == s.data.shape
    np.testing.assert_array_equal(back.mask, s.mask)
    assert np.array_equal(back.data, s.data, equal_nan=True)


def test_construct_from_numpy_and_roundtrip():
    arr = np.arange(12, dtype=np.float64).reshape(3, 4)
    arr[1, 2] = np.nan
    s = verity_x3p.Surface(arr, increment_x=1.5625, increment_y=2.0, creator="t")
    assert (s.ny, s.nx) == (3, 4)
    assert bool(s.mask[1, 2]) is False
    with tempfile.TemporaryDirectory() as d:
        p = str(Path(d) / "s.x3p")
        verity_x3p.write_x3p(s, p)
        back = verity_x3p.read_x3p(p)
    assert back.increment_x == 1.5625
    assert back.increment_y == 2.0
    assert np.array_equal(back.data, arr, equal_nan=True)


if __name__ == "__main__":
    test_read_real_fixture()
    test_roundtrip_file()
    test_construct_from_numpy_and_roundtrip()
    print("OK: all binding smoke tests passed")
