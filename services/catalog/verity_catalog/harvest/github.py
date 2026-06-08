"""GitHub repository source adapter.

For datasets published as plain files in a public GitHub repo (rather than a data
registry). Lists one directory via the Contents API
(``/repos/{owner}/{repo}/contents/{path}``), which returns each file with its raw
``download_url`` on ``raw.githubusercontent.com``, then fetches the bytes from
that CDN URL.

One API call lists the directory — well within the 60/hr unauthenticated limit —
and the file downloads hit the CDN, which is not API-rate-limited. So a full
ingest needs no token. Used for the CSAFE-ISU cartridge-case X3P scans, versioned
directly in ``github.com/CSAFE-ISU/cartridgeCaseScans``.
"""

from __future__ import annotations

from .base import RemoteFile, fetch_url

GITHUB_API = "https://api.github.com"
_USER_AGENT = "verity-catalog/0.1 (+https://github.com/erichare/verity)"


class GithubSource:
    """Lists and fetches the files of one directory in a public GitHub repo."""

    def __init__(
        self,
        repo: str,
        *,
        ref: str = "main",
        path: str = "",
        suffix: str = ".x3p",
        timeout: float = 120.0,
        request_delay: float = 0.6,
        retries: int = 4,
    ):
        self.repo = repo.strip("/")  # "owner/name"
        self.ref = ref
        self.path = path.strip("/")
        self.suffix = suffix
        self._timeout = timeout
        self._request_delay = request_delay
        self._retries = retries

    def discover(self) -> list[RemoteFile]:
        import httpx

        url = f"{GITHUB_API}/repos/{self.repo}/contents/{self.path}"
        resp = httpx.get(
            url,
            params={"ref": self.ref},
            headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        entries = resp.json()
        if not isinstance(entries, list):
            # The Contents API returns an object (not a list) when ``path`` is a
            # file rather than a directory.
            raise ValueError(f"{self.repo}/{self.path}@{self.ref} is not a directory listing")
        return [
            RemoteFile(name=entry["name"], url=entry["download_url"], size=entry.get("size"))
            for entry in entries
            if entry.get("type") == "file"
            and entry.get("download_url")
            and entry["name"].endswith(self.suffix)
        ]

    def fetch(self, file: RemoteFile) -> bytes:
        return fetch_url(
            file.url,
            timeout=self._timeout,
            request_delay=self._request_delay,
            retries=self._retries,
            user_agent=_USER_AGENT,
        )
