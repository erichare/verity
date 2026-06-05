"""Source adapter interface and a simple URL-list source."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass
class RemoteFile:
    """A fetchable scan file at a source."""

    name: str
    url: str
    size: int | None = None
    md5: str | None = None


class Source(Protocol):
    """Discovers the files in a dataset and fetches their bytes."""

    def discover(self) -> Iterable[RemoteFile]: ...

    def fetch(self, file: RemoteFile) -> bytes: ...


class UrlListSource:
    """Fetches an explicit list of files by URL — e.g. the NBTRD direct
    ``DownloadMeasurement/{guid}`` endpoints declared in a manifest. (Discovering
    those GUIDs by crawling NBTRD is the separate Phase-D harvester.)"""

    def __init__(self, files: list[RemoteFile], *, timeout: float = 120.0):
        self._files = files
        self._timeout = timeout

    def discover(self) -> list[RemoteFile]:
        return list(self._files)

    def fetch(self, file: RemoteFile) -> bytes:
        import httpx

        resp = httpx.get(file.url, follow_redirects=True, timeout=self._timeout)
        resp.raise_for_status()
        return resp.content
