"""The local MCP transport owns path-opened files and bounds HTTP waits."""

import io

import pytest

from verity_mcp.api import VerityAPI


class RecordingSession:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.files = []
        self.timeout = None

    def get(self, url, **kwargs):
        return self.post(url, **kwargs)

    def post(self, url, **kwargs):
        self.timeout = kwargs.get("timeout")
        files = kwargs.get("files", [])
        values = files.values() if isinstance(files, dict) else [v for _, v in files]
        self.files.extend(value[1] for value in values)
        assert all(not f.closed for f in self.files)
        if self.fail:
            raise RuntimeError("transport failed")
        return self

    status_code = 200

    def json(self):
        return {"status": "ok"}


@pytest.mark.parametrize("operation", ["detect", "compare"])
@pytest.mark.parametrize("fail", [False, True])
def test_path_files_closed_even_when_http_fails(tmp_path, operation, fail):
    scan = tmp_path / "scan.x3p"
    scan.write_bytes(b"scan")
    session = RecordingSession(fail=fail)
    api = VerityAPI(session=session)

    def invoke():
        if operation == "detect":
            return api.detect(scan)
        return api.compare("impressed", [scan], [scan])

    if fail:
        with pytest.raises(RuntimeError, match="transport failed"):
            invoke()
    else:
        invoke()
    assert all(f.closed for f in session.files)
    assert session.timeout is not None


def test_caller_stream_stays_open():
    scan = io.BytesIO(b"scan")
    VerityAPI(session=RecordingSession()).detect(scan)
    assert not scan.closed


def test_get_uses_timeout():
    session = RecordingSession()
    VerityAPI(session=session).health()
    assert session.timeout is not None


def test_missing_second_file_closes_first(tmp_path, monkeypatch):
    scan = tmp_path / "scan.x3p"
    scan.write_bytes(b"scan")
    import builtins

    original_open = builtins.open
    opened = []

    def recording_open(*args, **kwargs):
        result = original_open(*args, **kwargs)
        opened.append(result)
        return result

    monkeypatch.setattr(builtins, "open", recording_open)
    with pytest.raises(FileNotFoundError):
        VerityAPI(session=RecordingSession()).compare(
            "impressed", [scan], [scan.with_name("absent")]
        )
    assert opened and all(f.closed for f in opened)
