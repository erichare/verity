"""Upload-safety limits: zip-bomb guard, size/count caps, content-type checks."""

from __future__ import annotations

import dataclasses
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from verity_api import limits
from verity_api.limits import (
    LIMITS,
    NotAnX3P,
    UploadTooLarge,
    validate_x3p,
)
from verity_api.main import app

client = TestClient(app)

_FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "csafe-logo.x3p"


def _zip_bytes(name: str, payload: bytes) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, payload)
    return buf.getvalue()


def test_validate_accepts_real_x3p():
    validate_x3p(_FIXTURE.read_bytes(), filename="csafe-logo.x3p")  # must not raise


def test_validate_rejects_non_zip():
    with pytest.raises(NotAnX3P):
        validate_x3p(b"definitely not a zip file", filename="bad.x3p")


def test_validate_rejects_zip_bomb_by_ratio():
    bomb = _zip_bytes("bindata/data.bin", b"\x00" * (4 * 1024 * 1024))  # 4 MiB of zeros
    tight = dataclasses.replace(LIMITS, max_compression_ratio=10.0)
    with pytest.raises(UploadTooLarge):
        validate_x3p(bomb, filename="bomb.x3p", limits=tight)


def test_validate_rejects_oversized_decompressed():
    payload = _zip_bytes("bindata/data.bin", b"ABCD" * 1024)  # 4 KiB uncompressed
    tight = dataclasses.replace(LIMITS, max_uncompressed_bytes=1024)
    with pytest.raises(UploadTooLarge):
        validate_x3p(payload, filename="big.x3p", limits=tight)


def test_compare_rejects_oversized_file(monkeypatch):
    monkeypatch.setattr(limits, "LIMITS", dataclasses.replace(LIMITS, max_file_bytes=16))
    r = client.post(
        "/compare",
        data={"domain": "striated"},
        files={
            "mark_a": ("a.x3p", b"x" * 64, "application/octet-stream"),
            "mark_b": ("b.x3p", b"y" * 64, "application/octet-stream"),
        },
    )
    assert r.status_code == 413


def test_compare_rejects_too_many_files(monkeypatch):
    monkeypatch.setattr(limits, "LIMITS", dataclasses.replace(LIMITS, max_files=1))
    r = client.post(
        "/compare",
        data={"domain": "striated"},
        files=[
            ("mark_a", ("a.x3p", b"x", "application/octet-stream")),
            ("mark_a", ("a2.x3p", b"x", "application/octet-stream")),
            ("mark_b", ("b.x3p", b"y", "application/octet-stream")),
        ],
    )
    assert r.status_code == 413


def test_compare_rejects_too_many_files_combined(monkeypatch):
    # neither mark alone exceeds max_files, but the two together do
    monkeypatch.setattr(limits, "LIMITS", dataclasses.replace(LIMITS, max_files=3))
    files = [
        ("mark_a", ("a1.x3p", b"x", "application/octet-stream")),
        ("mark_a", ("a2.x3p", b"x", "application/octet-stream")),
        ("mark_b", ("b1.x3p", b"y", "application/octet-stream")),
        ("mark_b", ("b2.x3p", b"y", "application/octet-stream")),
    ]
    r = client.post("/compare", data={"domain": "striated"}, files=files)
    assert r.status_code == 413


def test_compare_rejects_non_x3p_content():
    r = client.post(
        "/compare",
        data={"domain": "striated"},
        files={
            "mark_a": ("a.x3p", b"not an x3p at all", "application/octet-stream"),
            "mark_b": ("b.x3p", b"also not", "application/octet-stream"),
        },
    )
    assert r.status_code == 415
