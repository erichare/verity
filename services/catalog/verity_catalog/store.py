"""Content-addressed blob store.

Scans are addressed by the SHA-256 of their bytes, so storage is
deduplicated, path-independent, and self-verifying — the same content hash that
the catalog records and the REST API serves as an ``ETag``. The interface is
backend-agnostic; only ``LocalBlobStore`` (filesystem) ships today, with S3/MinIO
intended for the deploy path.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path

from .config import Settings, get_settings


def sha256_hex(data: bytes) -> str:
    """SHA-256 of ``data`` as lowercase hex — the canonical content address."""
    return hashlib.sha256(data).hexdigest()


class BlobStore(ABC):
    """Stores immutable byte blobs keyed by their SHA-256 content hash."""

    @abstractmethod
    def put(self, data: bytes) -> str:
        """Store ``data`` (idempotently) and return its content hash."""

    @abstractmethod
    def get(self, content_hash: str) -> bytes:
        """Return the bytes for ``content_hash``; raise ``KeyError`` if absent."""

    @abstractmethod
    def exists(self, content_hash: str) -> bool: ...

    @abstractmethod
    def count(self) -> int:
        """Number of stored blobs."""


class LocalBlobStore(BlobStore):
    """Filesystem store. Blobs live at ``root/<ab>/<cd>/<hash>.bin`` (sharded by
    the first two hash bytes to keep directories small). Writes are atomic via a
    temp file + ``os.replace``, so a crash never leaves a partial blob."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _path(self, content_hash: str) -> Path:
        return self.root / content_hash[:2] / content_hash[2:4] / f"{content_hash}.bin"

    def put(self, data: bytes) -> str:
        content_hash = sha256_hex(data)
        path = self._path(content_hash)
        if path.exists():
            return content_hash  # dedup: identical content already stored
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, path)  # atomic publish
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return content_hash

    def get(self, content_hash: str) -> bytes:
        path = self._path(content_hash)
        if not path.exists():
            raise KeyError(content_hash)
        return path.read_bytes()

    def exists(self, content_hash: str) -> bool:
        return self._path(content_hash).exists()

    def count(self) -> int:
        if not self.root.exists():
            return 0
        return sum(1 for _ in self.root.rglob("*.bin"))


def get_store(settings: Settings | None = None) -> BlobStore:
    """Construct the configured blob store."""
    settings = settings or get_settings()
    if settings.blob_store_backend == "local":
        return LocalBlobStore(settings.blob_store_path)
    raise ValueError(f"unknown blob_store_backend: {settings.blob_store_backend!r}")
