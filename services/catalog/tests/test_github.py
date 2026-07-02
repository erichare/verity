import pytest

httpx = pytest.importorskip("httpx")

from verity_catalog.harvest.github import GithubSource  # noqa: E402


class _FakeResp:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_discover_lists_x3p_with_raw_urls(monkeypatch):
    payload = [
        {
            "name": "Fadul 1-1.x3p",
            "type": "file",
            "size": 100,
            "download_url": "https://raw.githubusercontent.com/o/r/main/d/Fadul%201-1.x3p",
        },
        {
            "name": "Fadul A.x3p",  # questioned, but still a .x3p the source returns
            "type": "file",
            "size": 90,
            "download_url": "https://raw.githubusercontent.com/o/r/main/d/Fadul%20A.x3p",
        },
        {  # non-.x3p file is filtered out
            "name": "README.md",
            "type": "file",
            "size": 10,
            "download_url": "https://raw.githubusercontent.com/o/r/main/d/README.md",
        },
        {"name": "nested", "type": "dir", "download_url": None},  # dirs filtered out
    ]
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return _FakeResp(payload)

    monkeypatch.setattr(httpx, "get", fake_get)

    files = GithubSource("CSAFE-ISU/cartridgeCaseScans", ref="main", path="fadulMasked").discover()

    assert [f.name for f in files] == ["Fadul 1-1.x3p", "Fadul A.x3p"]
    assert files[0].url.endswith("Fadul%201-1.x3p")
    assert files[0].size == 100
    assert (
        captured["url"]
        == "https://api.github.com/repos/CSAFE-ISU/cartridgeCaseScans/contents/fadulMasked"
    )
    assert captured["params"] == {"ref": "main"}


def test_discover_non_directory_raises(monkeypatch):
    # The Contents API returns an object (not a list) when the path is a file.
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp({"name": "x", "type": "file"}))
    with pytest.raises(ValueError, match="not a directory"):
        GithubSource("o/r", path="some/file.x3p").discover()


# --- recursive mode: one git/trees?recursive=1 call ------------------------- #
_TREE_PAYLOAD = {
    "sha": "abc123",
    "truncated": False,
    "tree": [
        {"path": "README.md", "type": "blob", "size": 10},  # wrong suffix
        {"path": "wellerMasked", "type": "tree"},  # directories filtered out
        {"path": "wellerMasked/TW01", "type": "tree"},
        {"path": "wellerMasked/TW01/TW01-01.x3p", "type": "blob", "size": 100},
        {"path": "wellerMasked/TW01/TW01-02.x3p", "type": "blob", "size": 101},
        {"path": "wellerMasked/TW02/TW02-01.x3p", "type": "blob", "size": 102},
        {"path": "wellerMasked/notes.txt", "type": "blob", "size": 5},  # wrong suffix
        # outside the requested path -> filtered out
        {"path": "fadulMasked/Fadul 1-1.x3p", "type": "blob", "size": 99},
    ],
}


def test_recursive_discover_walks_subdirectories(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return _FakeResp(_TREE_PAYLOAD)

    monkeypatch.setattr(httpx, "get", fake_get)

    files = GithubSource(
        "CSAFE-ISU/cartridgeCaseScans", ref="main", path="wellerMasked", recursive=True
    ).discover()

    # one API call, to the git-trees endpoint, with recursive=1
    assert (
        captured["url"]
        == "https://api.github.com/repos/CSAFE-ISU/cartridgeCaseScans/git/trees/main"
    )
    assert captured["params"] == {"recursive": "1"}
    # names preserve the path-relative subdirectory; other paths/suffixes filtered
    assert [f.name for f in files] == [
        "TW01/TW01-01.x3p",
        "TW01/TW01-02.x3p",
        "TW02/TW02-01.x3p",
    ]
    assert files[0].size == 100
    # download URLs are the raw-CDN form the Contents API would have returned
    assert files[0].url == (
        "https://raw.githubusercontent.com/CSAFE-ISU/cartridgeCaseScans/main/"
        "wellerMasked/TW01/TW01-01.x3p"
    )


def test_recursive_discover_percent_encodes_raw_urls(monkeypatch):
    payload = {
        "truncated": False,
        "tree": [{"path": "d/TW 01/TW 01-01.x3p", "type": "blob", "size": 1}],
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp(payload))

    files = GithubSource("o/r", path="d", recursive=True).discover()

    assert files[0].name == "TW 01/TW 01-01.x3p"
    assert files[0].url == "https://raw.githubusercontent.com/o/r/main/d/TW%2001/TW%2001-01.x3p"


def test_recursive_discover_without_path_lists_whole_tree(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp(_TREE_PAYLOAD))

    files = GithubSource("o/r", recursive=True).discover()

    assert [f.name for f in files] == [
        "wellerMasked/TW01/TW01-01.x3p",
        "wellerMasked/TW01/TW01-02.x3p",
        "wellerMasked/TW02/TW02-01.x3p",
        "fadulMasked/Fadul 1-1.x3p",
    ]


def test_recursive_discover_refuses_truncated_listing(monkeypatch):
    # A truncated tree is a PARTIAL listing — proceeding would silently drop
    # files from the ingest's completeness accounting, so it must raise.
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _FakeResp({"truncated": True, "tree": []})
    )
    with pytest.raises(ValueError, match="truncated"):
        GithubSource("o/r", path="d", recursive=True).discover()


def test_recursive_discover_rejects_malformed_response(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp({"message": "Not Found"}))
    with pytest.raises(ValueError, match="unexpected git tree response"):
        GithubSource("o/r", path="d", recursive=True).discover()


def test_flat_mode_still_uses_contents_api(monkeypatch):
    """Backward compat: recursive defaults to False and hits the Contents API."""
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        return _FakeResp([])

    monkeypatch.setattr(httpx, "get", fake_get)

    src = GithubSource("o/r", path="fadulMasked")

    assert src.recursive is False
    assert src.discover() == []
    assert captured["url"] == "https://api.github.com/repos/o/r/contents/fadulMasked"
