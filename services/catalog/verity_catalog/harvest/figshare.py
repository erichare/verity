"""Figshare source adapter (public ``api.figshare.com``).

Many forensic X3P datasets are openly downloadable from Figshare with real files.
Note that some — notably the Hamby sets on the Iowa State instance — are
*metadata-only* records whose data must be requested by email; we surface that
as a clear error rather than silently returning nothing.
"""

from __future__ import annotations

from .base import RemoteFile

FIGSHARE_API = "https://api.figshare.com/v2"


class FigshareSource:
    def __init__(self, article_id: int, *, timeout: float = 120.0):
        self.article_id = article_id
        self._timeout = timeout

    def discover(self) -> list[RemoteFile]:
        import httpx

        resp = httpx.get(f"{FIGSHARE_API}/articles/{self.article_id}", timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("is_metadata_record"):
            raise ValueError(
                f"Figshare article {self.article_id} ({data.get('title')!r}) is a "
                "metadata-only record with no downloadable files — the data must be "
                "obtained another way (e.g. emailing the contributor)."
            )
        return [
            RemoteFile(
                name=f["name"],
                url=f["download_url"],
                size=f.get("size"),
                md5=f.get("computed_md5") or f.get("supplied_md5"),
            )
            for f in data.get("files", [])
        ]

    def fetch(self, file: RemoteFile) -> bytes:
        import httpx

        resp = httpx.get(file.url, follow_redirects=True, timeout=self._timeout)
        resp.raise_for_status()
        return resp.content
