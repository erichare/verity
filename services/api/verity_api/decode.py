"""Shared low-level helpers: X3P decode and the engine version.

Extracted so both the comparison routes (``main``) and the glass-box step API
(``steps``) can decode a scan and stamp provenance without importing each other.
"""

from __future__ import annotations

import os
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import verity_x3p
from fastapi import HTTPException

from verity.surface import Surface


def engine_version() -> str:
    """The installed ``verity`` engine version, for provenance (``"unknown"`` if absent)."""
    try:
        return version("verity")
    except PackageNotFoundError:
        return "unknown"


def surface_from_bytes(data: bytes) -> Surface:
    """Decode raw X3P bytes into a :class:`Surface` via the native codec. Raises a clean
    400 on a bad upload (the bytes are validated as X3P upstream by ``limits``)."""
    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        s = verity_x3p.read_x3p(path)
        return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)
    except Exception as exc:  # noqa: BLE001 - surface a clean 400 for a bad upload
        raise HTTPException(status_code=400, detail=f"could not read X3P: {exc}") from exc
    finally:
        os.remove(path)
