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
