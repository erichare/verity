"""REST API tests against the *real* local catalog (SQLite + .verity/blobs).

These run with the default local-first config, so they exercise the same DB and
blob store the CLI uses. Concrete ids/values are discovered by querying the
catalog first (no hard-coded magic that could drift). Requires the `api` extra:

    uv run --extra api pytest tests/test_api.py
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from verity_catalog import models  # noqa: E402
from verity_catalog.api.app import app  # noqa: E402
from verity_catalog.db import engine  # noqa: E402
from verity_catalog.store import get_store  # noqa: E402


def _catalog_scan_count() -> int:
    """The live scan count in the local catalog — the catalog grows (bullets,
    cartridges, tool marks), so assert against the real count, not a frozen one."""
    with Session(engine) as session:
        return len(session.exec(select(models.Scan)).all())


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def a_scan() -> models.Scan:
    """A real scan row from the catalog whose blob is present locally."""
    store = get_store()
    with Session(engine) as session:
        scans = session.exec(select(models.Scan).order_by(models.Scan.id)).all()
        for scan in scans:
            if store.exists(scan.content_hash):
                return scan
    pytest.skip("no scan with a present blob in the local store")


# --- meta ------------------------------------------------------------------- #
def test_healthz_ok_with_store_count(client: TestClient):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["status"] == "ok"
    assert data["store_count"] == get_store().count()
    assert data["scan_count"] == _catalog_scan_count()
    assert data["store_backend"] == "local"
    assert data["database"] == "sqlite"


def test_version(client: TestClient):
    body = client.get("/version").json()
    assert body["success"] is True
    assert body["data"]["name"] == "verity-catalog"
    assert body["data"]["version"]


# --- studies / firearms ----------------------------------------------------- #
def test_list_studies_paginated(client: TestClient):
    body = client.get("/studies", params={"limit": 2}).json()
    assert body["success"] is True
    assert len(body["data"]) <= 2
    assert body["meta"]["total"] >= 1
    assert body["meta"]["limit"] == 2
    assert body["meta"]["page"] == 1


def test_get_study_and_404(client: TestClient):
    listed = client.get("/studies", params={"limit": 1}).json()["data"]
    study_id = listed[0]["id"]
    got = client.get(f"/studies/{study_id}").json()
    assert got["success"] is True
    assert got["data"]["id"] == study_id

    missing = client.get("/studies/99999999")
    assert missing.status_code == 404
    assert missing.json() == {
        "success": False,
        "data": None,
        "error": "study 99999999 not found",
        "meta": None,
    }


def test_list_firearms_filtered_by_study(client: TestClient):
    study_id = client.get("/studies", params={"limit": 1}).json()["data"][0]["id"]
    body = client.get("/firearms", params={"study_id": study_id}).json()
    assert body["success"] is True
    assert all(f["study_id"] == study_id for f in body["data"])


# --- scans: facets, metadata ----------------------------------------------- #
def test_list_scans_returns_rows(client: TestClient):
    body = client.get("/scans", params={"limit": 5}).json()
    assert body["success"] is True
    assert len(body["data"]) == 5
    assert body["meta"]["total"] == _catalog_scan_count()


def test_scans_respects_caliber_facet(client: TestClient):
    # Discover a real caliber from the catalog, then assert the facet narrows.
    with Session(engine) as session:
        caliber = session.exec(
            select(models.Firearm.caliber).where(models.Firearm.caliber.is_not(None))
        ).first()
    body = client.get("/scans", params={"caliber": caliber, "limit": 5}).json()
    assert body["success"] is True
    assert body["meta"]["total"] >= 1
    # A bogus caliber yields zero matches.
    none_body = client.get("/scans", params={"caliber": "no-such-caliber"}).json()
    assert none_body["meta"]["total"] == 0
    assert none_body["data"] == []


def test_scans_respects_source_and_resolution_facets(client: TestClient):
    src = client.get("/scans", params={"limit": 1}).json()["data"][0]["source"]
    body = client.get("/scans", params={"source": src, "limit": 3}).json()
    assert body["success"] is True
    assert all(s["source"] == src for s in body["data"])
    # min_resolution above any real value -> empty.
    hi = client.get("/scans", params={"min_resolution": 1e9}).json()
    assert hi["meta"]["total"] == 0


def test_scans_limit_capped_at_200(client: TestClient):
    # limit beyond the cap is a validation error -> enveloped 422.
    resp = client.get("/scans", params={"limit": 5000})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]


def test_get_scan_metadata(client: TestClient, a_scan: models.Scan):
    body = client.get(f"/scans/{a_scan.id}").json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"] == a_scan.id
    assert data["content_hash"] == a_scan.content_hash
    assert data["modality"] == a_scan.modality
    assert data["size_bytes"] == a_scan.size_bytes


def test_get_scan_404(client: TestClient):
    resp = client.get("/scans/99999999")
    assert resp.status_code == 404
    assert resp.json()["success"] is False


# --- scans: X3P blob with ETag + conditional 304 --------------------------- #
def test_scan_x3p_returns_bytes_with_etag(client: TestClient, a_scan: models.Scan):
    resp = client.get(f"/scans/{a_scan.id}/x3p")
    assert resp.status_code == 200
    assert resp.headers["etag"] == f'"{a_scan.content_hash}"'
    assert len(resp.content) == a_scan.size_bytes
    # bytes are content-addressed: hashing them reproduces the ETag.
    from verity_catalog.store import sha256_hex

    assert sha256_hex(resp.content) == a_scan.content_hash


def test_scan_x3p_if_none_match_yields_304(client: TestClient, a_scan: models.Scan):
    etag = f'"{a_scan.content_hash}"'
    resp = client.get(
        f"/scans/{a_scan.id}/x3p",
        headers={"If-None-Match": etag},
    )
    assert resp.status_code == 304
    assert resp.headers["etag"] == etag
    assert resp.content == b""


def test_scan_x3p_404_for_missing_scan(client: TestClient):
    resp = client.get("/scans/99999999/x3p")
    assert resp.status_code == 404
    assert resp.json()["success"] is False


# --- bullets / lands -------------------------------------------------------- #
def test_bullet_lands(client: TestClient, a_scan: models.Scan):
    # a_scan is a bullet scan, so it has a land -> bullet.
    with Session(engine) as session:
        scan = session.get(models.Scan, a_scan.id)
        bullet_id = scan.land.bullet_id
    body = client.get(f"/bullets/{bullet_id}/lands").json()
    assert body["success"] is True
    assert len(body["data"]) >= 1
    assert all(land["bullet_id"] == bullet_id for land in body["data"])


# --- datasets: pinned list with content hashes ----------------------------- #
def test_list_datasets(client: TestClient):
    body = client.get("/datasets").json()
    assert body["success"] is True
    names = {d["name"] for d in body["data"]}
    assert "hamby-252" in names


def test_dataset_resolves_to_pinned_hashes(client: TestClient):
    body = client.get("/datasets/hamby-252").json()
    assert body["success"] is True
    data = body["data"]
    assert data["name"] == "hamby-252"
    assert data["n_files"] >= 1
    assert data["n_resolved"] >= 1
    # at least one entry is pinned with a content hash matching the catalog.
    pinned = [f for f in data["files"] if f["content_hash"]]
    assert pinned, "expected resolved files to carry content hashes"
    sample = pinned[0]
    assert sample["scan_id"] is not None
    assert len(sample["content_hash"]) == 64
    with Session(engine) as session:
        scan = session.get(models.Scan, sample["scan_id"])
    assert scan.content_hash == sample["content_hash"]
    assert scan.source_ref == sample["url"]


def test_dataset_404(client: TestClient):
    resp = client.get("/datasets/no-such-dataset")
    assert resp.status_code == 404
    assert resp.json()["success"] is False
