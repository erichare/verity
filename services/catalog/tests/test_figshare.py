import pytest

httpx = pytest.importorskip("httpx")

from verity_catalog.harvest.figshare import FigshareSource  # noqa: E402


class _FakeResp:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_discover_lists_files(monkeypatch):
    payload = {
        "is_metadata_record": False,
        "title": "Open X3P set",
        "files": [
            {"name": "a.x3p", "download_url": "https://x/a", "size": 10, "computed_md5": "abc"},
            {"name": "b.x3p", "download_url": "https://x/b", "size": 20},
        ],
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp(payload))
    files = FigshareSource(123).discover()
    assert [f.name for f in files] == ["a.x3p", "b.x3p"]
    assert files[0].url == "https://x/a"
    assert files[0].md5 == "abc"


def test_metadata_only_record_raises(monkeypatch):
    payload = {"is_metadata_record": True, "title": "Hamby 44 Ruger P-85 LEA scans", "files": []}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _FakeResp(payload))
    with pytest.raises(ValueError, match="metadata-only"):
        FigshareSource(11366003).discover()
