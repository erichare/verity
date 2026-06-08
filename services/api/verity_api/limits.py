"""Upload-safety limits for the public API.

Treat every upload as hostile: cap the bytes read into memory, the number of files,
the total request size, and — because an X3P is a ZIP container the native reader
expands — the *decompressed* size and compression ratio (a zip-bomb guard). All
thresholds come from the environment with conservative defaults, validated at import
so a misconfiguration fails fast at startup rather than mid-request.

These helpers stay framework-light: they raise :class:`UploadRejected` (with an HTTP
status), and the API maps that to a clean JSON error.
"""

from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from io import BytesIO

_ZIP_MAGIC = b"PK\x03\x04"
_CHUNK = 1 << 20  # 1 MiB streaming read
_MiB = 1 << 20


class UploadRejected(Exception):
    """An upload that violates a safety limit. ``status_code`` is the HTTP status the
    API should return."""

    status_code = 413

    def __init__(self, detail: str, *, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code


class UploadTooLarge(UploadRejected):
    status_code = 413


class TooManyFiles(UploadRejected):
    status_code = 413


class NotAnX3P(UploadRejected):
    status_code = 415


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


@dataclass(frozen=True)
class UploadLimits:
    """Resolved upload-safety thresholds. Build with :meth:`from_env`."""

    max_file_bytes: int
    max_total_bytes: int
    max_files: int
    max_uncompressed_bytes: int
    max_compression_ratio: float
    compare_timeout_s: float
    max_concurrency: int
    rate_limit: int
    rate_window_s: float

    @classmethod
    def from_env(cls) -> UploadLimits:
        cpu = os.cpu_count() or 2
        return cls(
            max_file_bytes=_env_int("VERITY_MAX_FILE_BYTES", 64 * _MiB),
            max_total_bytes=_env_int("VERITY_MAX_UPLOAD_BYTES", 256 * _MiB),
            max_files=_env_int("VERITY_MAX_FILES", 24),
            max_uncompressed_bytes=_env_int("VERITY_MAX_UNCOMPRESSED_BYTES", 512 * _MiB),
            max_compression_ratio=_env_float("VERITY_MAX_COMPRESSION_RATIO", 200.0),
            compare_timeout_s=_env_float("VERITY_COMPARE_TIMEOUT_S", 60.0),
            max_concurrency=_env_int("VERITY_MAX_CONCURRENCY", max(2, min(4, cpu - 1))),
            rate_limit=_env_int("VERITY_RATE_LIMIT", 120),
            rate_window_s=_env_float("VERITY_RATE_WINDOW_S", 60.0),
        )


# Resolved once at import — a bad value fails startup, not a live request.
LIMITS = UploadLimits.from_env()


class ByteBudget:
    """A shared running cap on bytes read across a multi-file request."""

    def __init__(self, total: int) -> None:
        self.remaining = total

    def take(self, n: int) -> None:
        self.remaining -= n
        if self.remaining < 0:
            raise UploadTooLarge("total upload size exceeds the limit")


async def read_capped(upload, *, file_cap: int, budget: ByteBudget) -> bytes:
    """Stream an upload into memory, aborting as soon as it exceeds ``file_cap`` or the
    shared ``budget`` — so a hostile multi-GB body never fully materializes."""
    buf = bytearray()
    while True:
        chunk = await upload.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)  # in-place; avoids repeated reallocation
        if len(buf) > file_cap:
            raise UploadTooLarge(f"a file exceeds the {file_cap}-byte per-file limit")
        budget.take(len(chunk))
    return bytes(buf)


def validate_x3p(data: bytes, *, filename: str, limits: UploadLimits | None = None) -> None:
    """Reject anything that is not a sane X3P before it reaches the native reader: the
    ZIP magic, the *actual* decompressed size, and the compression ratio (zip-bomb
    guard). We stream-decompress each member and count real bytes — the central-
    directory ``file_size`` is attacker-controlled, so it is never trusted."""
    lim = limits or LIMITS
    name = (filename or "upload")[:200]  # bound reflected length
    if not data.startswith(_ZIP_MAGIC):
        raise NotAnX3P(f"{name} is not an X3P file (an X3P is a ZIP container)")
    uncompressed = 0
    compressed = 0
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            for info in zf.infolist():
                compressed += info.compress_size
                with zf.open(info) as member:
                    while True:
                        chunk = member.read(_CHUNK)
                        if not chunk:
                            break
                        uncompressed += len(chunk)
                        if uncompressed > lim.max_uncompressed_bytes:
                            raise UploadTooLarge(
                                f"{name} decompresses past the "
                                f"{lim.max_uncompressed_bytes}-byte limit (zip bomb?)"
                            )
    except zipfile.BadZipFile as exc:
        raise NotAnX3P(f"{name} is not a readable X3P: {str(exc)[:200]}") from exc
    ratio = uncompressed / (compressed or 1)
    if ratio > lim.max_compression_ratio:
        raise UploadTooLarge(f"{name} compression ratio {ratio:.0f}× exceeds the zip-bomb guard")
