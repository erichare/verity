"""Applicability-domain refusal: the public /compare paths must refuse to emit a
likelihood ratio for a scan outside the validated domain, and always annotate the
scope of admissible comparisons.

These are end-to-end tests through the FastAPI app: they synthesize real X3P uploads
with the native ``verity_x3p`` writer so the request exercises the same decode →
guard → score path as production."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import verity_x3p
from fastapi.testclient import TestClient

from verity_api.main import app

client = TestClient(app)


def _x3p_bytes(heights: np.ndarray, dx: float) -> bytes:
    """Encode a height grid to X3P bytes at lateral pitch ``dx`` (metres)."""
    s = verity_x3p.Surface(heights, increment_x=dx, increment_y=dx, creator="verity-test")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.x3p"
        verity_x3p.write_x3p(s, str(p))
        return p.read_bytes()


def _striated(seed: int, *, dx: float = 1.5e-6, nx: int = 256, ny: int = 256) -> bytes:
    """An in-domain striated land: striae well inside the roughness band, pitch that
    resolves it, full coverage, real amplitude."""
    rng = np.random.default_rng(seed)
    x = np.arange(nx)
    stripes = 0.5e-6 * np.sin(2 * np.pi * x / 12.0 + seed * 0.1)
    z = np.tile(stripes, (ny, 1)) + rng.normal(scale=0.03e-6, size=(ny, nx))
    return _x3p_bytes(z, dx)


def _coarse(seed: int = 0, nx: int = 256, ny: int = 256) -> bytes:
    """Same striae but scanned at 10 µm pitch — coarser than λ_s = 4 µm, so the
    individualizing roughness band cannot be resolved (hard resolution failure)."""
    return _striated(seed, dx=10e-6, nx=nx, ny=ny)


def _post(domain: str, a: bytes, b: bytes, *, path: str = "/compare", include: str | None = None):
    data = {"domain": domain}
    if include is not None:
        data["include"] = include
    return client.post(
        path,
        data=data,
        files={
            "mark_a": ("a.x3p", a, "application/octet-stream"),
            "mark_b": ("b.x3p", b, "application/octet-stream"),
        },
    )


def test_compare_refuses_coarse_pitch_out_of_domain():
    r = _post("striated", _coarse(), _coarse())
    assert r.status_code == 200
    body = r.json()
    assert body["refused"] is True
    assert "likelihood_ratio" not in body
    assert body["scope"]["mark_a"][0]["admissible"] is False
    assert "resolution" in body["reason"] or "resolve" in body["reason"]


def test_compare_refuses_wrong_modality():
    # A clearly striated mark sent under the impressed reference: the mark type picks
    # the calibration, so a modality mismatch is a hard refusal.
    r = _post("impressed", _striated(1), _striated(2))
    assert r.status_code == 200
    body = r.json()
    assert body["refused"] is True
    assert "likelihood_ratio" not in body
    assert any(not c["passed"] for c in body["scope"]["mark_a"][0]["checks"] if c["name"] == "modality")


def test_compare_admits_in_domain_and_attaches_scope():
    r = _post("striated", _striated(3), _striated(3))
    assert r.status_code == 200
    body = r.json()
    assert "refused" not in body
    assert "likelihood_ratio" in body
    # scope now rides along on admissible comparisons too (was v1-only before).
    assert "scope" in body
    assert body["scope"]["mark_a"][0]["admissible"] is True


def test_v1_compare_refuses_out_of_domain():
    r = _post("striated", _coarse(), _striated(1), path="/v1/compare", include="all")
    assert r.status_code == 200
    body = r.json()
    assert body["refused"] is True
    assert "likelihood_ratio" not in body


def test_compare_report_pdf_refuses_out_of_domain():
    r = _post("striated", _coarse(), _coarse(), path="/v1/compare/report.pdf")
    assert r.status_code == 422


def test_single_land_carries_diagnostic_flag():
    r = _post("striated", _striated(3), _striated(3))
    assert r.status_code == 200
    body = r.json()
    assert "likelihood_ratio" in body
    note = body["evidence_note"]
    assert note["single_land"] is True
    assert note["level"] == "diagnostic_only"


def test_multi_land_has_no_diagnostic_flag():
    files = [("mark_a", (f"a{i}.x3p", _striated(i), "application/octet-stream")) for i in range(4)]
    files += [("mark_b", (f"b{i}.x3p", _striated(i), "application/octet-stream")) for i in range(4)]
    r = client.post("/compare", data={"domain": "striated"}, files=files)
    assert r.status_code == 200
    body = r.json()
    assert "likelihood_ratio" in body
    assert "evidence_note" not in body
    # bullet_pooled now carries barrel cluster IDs → the public CI uses the honest
    # clustered bootstrap, and reports how many sources back it.
    assert body["lr_ci_method"] == "bootstrap-clustered"
    assert body["n_sources"] and body["n_sources"] > 1
