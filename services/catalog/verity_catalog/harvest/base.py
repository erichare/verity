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
    those GUIDs by crawling NBTRD is the separate Phase-D harvester.)

    Polite by default: a small inter-request delay plus bounded retries with
    backoff, suitable for pulling hundreds of files from a public ``.gov`` host."""

    USER_AGENT = "verity-catalog/0.1 (+https://github.com/erichare/verity)"

    def __init__(
        self,
        files: list[RemoteFile],
        *,
        timeout: float = 120.0,
        request_delay: float = 0.6,
        retries: int = 4,
    ):
        self._files = files
        self._timeout = timeout
        self._request_delay = request_delay
        self._retries = retries

    def discover(self) -> list[RemoteFile]:
        return list(self._files)

    def fetch(self, file: RemoteFile) -> bytes:
        import time

        import httpx

        headers = {"User-Agent": self.USER_AGENT}
        last_error: Exception | None = None
        for attempt in range(self._retries):
            if self._request_delay:
                time.sleep(self._request_delay)
            try:
                resp = httpx.get(
                    file.url, follow_redirects=True, timeout=self._timeout, headers=headers
                )
                resp.raise_for_status()
                return resp.content
            except httpx.HTTPError as err:
                last_error = err
                time.sleep(min(2.0**attempt, 10.0))  # backoff before retry
        raise RuntimeError(
            f"failed to fetch {file.url} after {self._retries} attempts"
        ) from last_error
