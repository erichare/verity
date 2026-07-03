"""The /scalar reference shell, /robots.txt, and app-wide HEAD support.

DB-free routes only (like ``test_security_headers``) so this runs on a fresh
clone / CI without a catalog database."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from verity_catalog.api.app import app  # noqa: E402

client = TestClient(app)


# --------------------------------------------------------------------------- #
# /scalar — the Evidence-themed reference shell (parity with api.verity.codes)
# --------------------------------------------------------------------------- #
def test_scalar_page_basics():
    r = client.get("/scalar")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert '<html lang="en">' in html
    assert "<title>Verity data API reference</title>" in html
    assert '<meta name="description" content="Verity data API' in html
    # og basics + favicon (the shared brand icon on the web host).
    assert 'property="og:title"' in html
    assert 'property="og:description"' in html
    assert 'property="og:url" content="https://data.verity.codes/scalar"' in html
    assert 'href="https://verity.codes/icon.svg"' in html
    # noscript fallback points at the raw OpenAPI document.
    assert "<noscript>" in html
    assert 'href="/openapi.json"' in html


def test_scalar_bundle_is_pinned_with_sri():
    html = client.get("/scalar").text
    assert "https://cdn.jsdelivr.net/npm/@scalar/api-reference@1.62.2" in html
    # No unpinned bundle reference remains.
    assert 'src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"' not in html
    assert 'integrity="sha384-' in html
    assert 'crossorigin="anonymous"' in html


def test_scalar_evidence_theme_tokens():
    """The same Evidence palette as the comparison API's reference page, with
    --scalar-color-3 darkened to meet WCAG AA (>= 4.5:1) on the light canvas."""
    html = client.get("/scalar").text
    assert "--scalar-background-1: #f4f1ea" in html  # canvas / bone
    assert "--scalar-color-accent: #0e2a47" in html  # navy primary
    assert '"theme":"none"' in html  # custom tokens take effect
    assert "--scalar-color-3: #626c7b" in html  # 4.71:1 on #f4f1ea
    assert "#8a93a3" in html  # dark-mode color-3 keeps the original (5.97:1)


# --------------------------------------------------------------------------- #
# /robots.txt — two lines, allow-all, no sitemap (API host)
# --------------------------------------------------------------------------- #
def test_robots_txt():
    r = client.get("/robots.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text == "User-agent: *\nAllow: /\n"


# --------------------------------------------------------------------------- #
# HEAD answers on every GET route (monitors / link checkers got 405 before)
# --------------------------------------------------------------------------- #
def test_head_matches_get_headers_with_empty_body():
    get = client.get("/version")
    head = client.head("/version")
    assert head.status_code == 200
    assert head.content == b""
    assert int(head.headers["content-length"]) == len(get.content)
    assert head.headers["content-type"] == get.headers["content-type"]


def test_head_on_scalar_and_robots():
    for path in ("/scalar", "/robots.txt"):
        head = client.head(path)
        assert head.status_code == 200, path
        assert head.content == b"", path
        assert int(head.headers["content-length"]) > 0, path


def test_head_unknown_path_is_404_not_405():
    assert client.head("/no-such-route").status_code == 404
