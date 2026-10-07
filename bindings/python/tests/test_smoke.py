"""Smoke tests for the verity_x3p Python binding.

Run directly (``python tests/test_smoke.py``) or under pytest.
"""

import hashlib
import tempfile
import xml.etree.ElementTree as ET
import zipfile
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


def test_roundtrip_preserves_axes_and_instrument_provenance(tmp_path):
    source = tmp_path / "source.x3p"
    verity_x3p.write_x3p(verity_x3p.Surface(np.zeros((2, 3))), source)
    with zipfile.ZipFile(source) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    root = ET.fromstring(members["main.xml"])
    fields = {
        "Record1/Axes/CX/Offset": "0.125",
        "Record1/Axes/CY/Offset": "-0.5",
        "Record1/Axes/CZ/Increment": "0.25",
        "Record1/Axes/CZ/Offset": "1.5",
        "Record2/Date": "2026-01-02T03:04:05",
        "Record2/Creator": "Fixture creator",
        "Record2/Instrument/Manufacturer": "Acme",
        "Record2/Instrument/Model": "Model & <1>",
        "Record2/Instrument/Serial": "S123",
        "Record2/Instrument/Version": "v2",
        "Record2/CalibrationDate": "2025-12-01",
        "Record2/ProbingSystem/Type": "Non-contact",
        "Record2/ProbingSystem/Identification": "Optical probe",
        "Record2/Comment": "Instrument provenance must survive",
    }
    for path, value in fields.items():
        root.find(path).text = value
    members["main.xml"] = ET.tostring(root)
    with zipfile.ZipFile(source, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)

    copied = tmp_path / "copy.x3p"
    verity_x3p.write_x3p(verity_x3p.read_x3p(source), copied)
    with zipfile.ZipFile(copied) as archive:
        copied_root = ET.fromstring(archive.read("main.xml"))
    for path, expected in fields.items():
        assert copied_root.findtext(path) == expected, path


def test_packed_validity_fixtures_and_roundtrip(tmp_path):
    mask = np.array([True, False, True, False, True, False, False, True, True, False])
    for code in "ILFD":
        scan = verity_x3p.read_x3p(FIXTURE.with_name(f"validity-{code.lower()}.x3p"))
        expected_mask = mask.copy()
        if code == "I":
            expected_heights = np.arange(-10, 0, dtype=float) * 0.5 + 100
        elif code == "L":
            expected_heights = np.arange(100000, 100010, dtype=float) * 0.5 + 100
        else:
            expected_heights = np.arange(10, dtype=float)
            expected_mask[2] = (
                False  # The validity bit is set but the coordinate is NaN.
            )
        expected_heights[~expected_mask] = np.nan
        np.testing.assert_array_equal(scan.mask, expected_mask.reshape(2, 5))
        np.testing.assert_array_equal(scan.data, expected_heights.reshape(2, 5))
        copy = tmp_path / f"copy-{code}.x3p"
        verity_x3p.write_x3p(scan, copy)
        back = verity_x3p.read_x3p(copy)
        np.testing.assert_array_equal(back.mask, scan.mask)
        np.testing.assert_array_equal(back.data, scan.data)


def test_validity_checksum_errors_are_python_value_errors(tmp_path):
    with zipfile.ZipFile(FIXTURE.with_name("validity-i.x3p")) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members["bindata/valid.bin"] = bytes([members["bindata/valid.bin"][0] ^ 1, 0xFD])
    corrupt = tmp_path / "corrupt.x3p"
    with zipfile.ZipFile(corrupt, "w") as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    with np.testing.assert_raises_regex(ValueError, "checksum mismatch.*valid.bin"):
        verity_x3p.read_x3p(corrupt)
    recovered = verity_x3p.read_x3p(corrupt, verify_checksums=False)
    assert not recovered.mask[0, 0]
    assert np.isnan(recovered.data[0, 0])


def test_existing_fixture_decoding_is_unchanged():
    scan = verity_x3p.read_x3p(FIXTURE)
    assert hashlib.sha256(scan.data.astype("<f8").tobytes()).hexdigest() == (
        "72f964b161efbb19754c2ef091a317cf643d2ca5a83d4265f55be5eb5d93290a"
    )
    assert hashlib.sha256(scan.mask.tobytes()).hexdigest() == (
        "8eeb7f836f96ab19b2797acf58132858543b584089f17fc66612111e526ad46a"
    )


if __name__ == "__main__":
    test_read_real_fixture()
    test_roundtrip_file()
    test_construct_from_numpy_and_roundtrip()
    print("OK: all binding smoke tests passed")
