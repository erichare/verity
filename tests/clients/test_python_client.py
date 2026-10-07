"""Offline regressions for HTTP bounds and multipart file ownership."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "clients" / "python"))
from verity_client import VerityClient, VerityError


class Response:
    status_code = 200
    text = ""

    def json(self):
        return {"handle": "sha256:fixture", "status": "ok"}


class Session:
    def __init__(self, error=None, status=200):
        self.error = error
        self.status = status
        self.files = []
        self.calls = []

    def request(self, url, **kwargs):
        self.calls.append((url, kwargs))
        fields = kwargs.get("files", [])
        if isinstance(fields, dict):
            fields = fields.items()
        self.files = [value[1] for _, value in fields]
        for stream in self.files:
            if stream.closed:
                raise AssertionError("file was closed before the request")
            stream.read()
        if self.error:
            raise self.error
        response = Response()
        response.status_code = self.status
        return response

    get = request
    post = request


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.scan = Path(self.temp.name) / "scan.x3p"
        self.scan.write_bytes(b"scan")

    def call_with_scan(self, client, operation, scan):
        if operation == "compare":
            return client.compare("impressed", scan, scan)
        return getattr(client, operation)(scan)

    def test_owned_files_close_after_success_or_request_errors(self):
        for operation in ("compare", "detect", "upload"):
            for error, status in ((None, 200), (OSError("offline"), 200), (None, 400)):
                with self.subTest(operation=operation, error=error, status=status):
                    session = Session(error=error, status=status)
                    client = VerityClient(session=session)
                    if error is not None or status >= 400:
                        with self.assertRaises((OSError, VerityError)):
                            self.call_with_scan(client, operation, self.scan)
                    else:
                        self.call_with_scan(client, operation, self.scan)
                    self.assertTrue(session.files)
                    self.assertTrue(all(stream.closed for stream in session.files))

    def test_partial_open_failure_closes_previous_files(self):
        opened = []

        def track_open(*args, **kwargs):
            stream = open(*args, **kwargs)  # noqa: SIM115 - exercise the client's ownership
            opened.append(stream)
            return stream

        with patch("verity_client.open", track_open, create=True), self.assertRaises(FileNotFoundError):
            VerityClient(session=Session()).compare(
                "impressed", self.scan, self.scan.with_name("missing.x3p")
            )
        self.assertEqual(len(opened), 1)
        self.assertTrue(opened[0].closed)

    def test_caller_streams_remain_open_on_success_and_failure(self):
        for operation in ("compare", "detect", "upload"):
            for error in (None, OSError("offline")):
                with self.subTest(operation=operation, error=error), io.BytesIO(b"scan") as stream:
                    client = VerityClient(session=Session(error=error))
                    if error:
                        with self.assertRaises(OSError):
                            self.call_with_scan(client, operation, stream)
                    else:
                        self.call_with_scan(client, operation, stream)
                    self.assertFalse(stream.closed)

    def test_timeout_applies_to_get_and_post(self):
        for timeout in (120, 300):
            session = Session()
            kwargs = {} if timeout == 120 else {"timeout": timeout}
            client = VerityClient(session=session, **kwargs)
            client.health()
            client.calibrate(0.5, "impressed")
            self.assertEqual([kw["timeout"] for _, kw in session.calls], [timeout, timeout])

    def test_invalid_timeout_fails_before_a_request(self):
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                VerityClient(session=Session(), timeout=timeout)

    def test_api_url_environment_and_explicit_override(self):
        with patch.dict(os.environ, {"VERITY_API_URL": "https://deployment.test/"}):
            session = Session()
            VerityClient(session=session).health()
            self.assertEqual(session.calls[-1][0], "https://deployment.test/health")
            VerityClient("", session=session).health()
            self.assertEqual(session.calls[-1][0], "/health")


if __name__ == "__main__":
    unittest.main()
