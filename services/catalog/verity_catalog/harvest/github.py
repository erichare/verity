"""GitHub repository source adapter.

For datasets published as plain files in a public GitHub repo (rather than a data
registry). Two listing modes, both a **single** API call:

- **Flat (default):** lists one directory via the Contents API
  (``/repos/{owner}/{repo}/contents/{path}``), which returns each file with its
  raw ``download_url`` on ``raw.githubusercontent.com``.
- **Recursive (``recursive=True``):** lists the whole subtree under ``path`` via
  the Git Trees API (``/repos/{owner}/{repo}/git/trees/{ref}?recursive=1``) —
  one call regardless of nesting depth, so walking N subdirectories costs no
  extra rate-limit budget. File names preserve the ``path``-relative
  subdirectory (e.g. ``TW01/TW01-01.x3p``), and the raw-CDN download URL is
  constructed the same way the Contents API's ``download_url`` is.

Either way one API call lists the dataset — well within the 60/hr
unauthenticated limit — and the file downloads hit the CDN, which is not
API-rate-limited. So a full ingest needs no token. Used for the CSAFE-ISU
cartridge-case X3P scans, versioned directly in
``github.com/CSAFE-ISU/cartridgeCaseScans``.
"""

from __future__ import annotations

from urllib.parse import quote

from .base import RemoteFile, fetch_url

GITHUB_API = "https://api.github.com"
GITHUB_RAW = "https://raw.githubusercontent.com"
_USER_AGENT = "verity-catalog/0.1 (+https://github.com/erichare/verity)"


class GithubSource:
    """Lists and fetches the files of one directory (optionally its whole
    subtree) in a public GitHub repo."""

    def __init__(
        self,
        repo: str,
        *,
        ref: str = "main",
        path: str = "",
        suffix: str = ".x3p",
        recursive: bool = False,
        timeout: float = 120.0,
        request_delay: float = 0.6,
        retries: int = 4,
    ):
        self.repo = repo.strip("/")  # "owner/name"
        self.ref = ref
        self.path = path.strip("/")
        self.suffix = suffix
        self.recursive = recursive
        self._timeout = timeout
        self._request_delay = request_delay
        self._retries = retries

    def discover(self) -> list[RemoteFile]:
        if self.recursive:
            return self._discover_tree()
        return self._discover_contents()

    def _discover_contents(self) -> list[RemoteFile]:
        """Flat mode: one Contents-API call listing exactly ``self.path``."""
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

    def _discover_tree(self) -> list[RemoteFile]:
        """Recursive mode: one Git-Trees API call for the ref's whole tree,
        filtered to blobs under ``self.path``.

        The single ``?recursive=1`` call keeps rate-limit cost independent of
        how many subdirectories the dataset has (the Contents API would need one
        call per directory). Requesting the tree of the plain ref — rather than
        the ``{ref}:{path}`` revision syntax — keeps the URL unambiguous; the
        ``path`` scoping happens client-side by prefix. Returned names are
        ``path``-relative, preserving the subdirectory (``TW01/TW01-01.x3p``).
        """
        import httpx

        url = f"{GITHUB_API}/repos/{self.repo}/git/trees/{quote(self.ref, safe='')}"
        resp = httpx.get(
            url,
            params={"recursive": "1"},
            headers={"Accept": "application/vnd.github+json", "User-Agent": _USER_AGENT},
            follow_redirects=True,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not isinstance(payload, dict) or "tree" not in payload:
            raise ValueError(f"unexpected git tree response for {self.repo}@{self.ref}")
        if payload.get("truncated"):
            # Never proceed on a partial listing: files silently missing from
            # the tree would corrupt the ingest's completeness accounting.
            raise ValueError(
                f"git tree listing for {self.repo}@{self.ref} was truncated by the API"
            )
        prefix = f"{self.path}/" if self.path else ""
        files: list[RemoteFile] = []
        for entry in payload["tree"]:
            entry_path = entry.get("path", "")
            if (
                entry.get("type") != "blob"
                or not entry_path.endswith(self.suffix)
                or not entry_path.startswith(prefix)
            ):
                continue
            name = entry_path[len(prefix) :]
            files.append(RemoteFile(name=name, url=self._raw_url(name), size=entry.get("size")))
        return files

    def _raw_url(self, name: str) -> str:
        """Raw-CDN download URL for a ``path``-relative file name — the same
        ``raw.githubusercontent.com`` form the Contents API's ``download_url``
        uses (percent-encoded; ``quote`` keeps ``/`` as the segment separator)."""
        full_path = f"{self.path}/{name}" if self.path else name
        return f"{GITHUB_RAW}/{self.repo}/{quote(self.ref, safe='')}/{quote(full_path)}"

    def fetch(self, file: RemoteFile) -> bytes:
        return fetch_url(
            file.url,
            timeout=self._timeout,
            request_delay=self._request_delay,
            retries=self._retries,
            user_agent=_USER_AGENT,
        )
