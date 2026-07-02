"""Hermetic API tests for the data-integrity fixes: per-scan blob availability
(list field + facet + honest 404), the study facet across all three mark
families (bullet lands, cartridge marks, toolmarks), dataset resolution for
discover-at-ingest manifests, and the self-documenting OpenAPI descriptions.

Runs on a tmp SQLite catalog + tmp local blob store via dependency overrides —
no populated local catalog needed (unlike ``test_api.py``)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("yaml")
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from verity_catalog import models  # noqa: E402
from verity_catalog.api import deps  # noqa: E402
from verity_catalog.api.app import app  # noqa: E402
from verity_catalog.ingest import load_manifest_by_name  # noqa: E402
from verity_catalog.store import LocalBlobStore, sha256_hex  # noqa: E402

PRESENT_BLOB = b"bullet scan bytes, synced"
MISSING_BLOB = b"bullet scan bytes, NOT synced"
FADUL_BLOB = b"fadul breech-face bytes, NOT synced"
TMARKS_BLOB = b"tmarks 1-D profile bytes, NOT synced"
MIXED_LAND_BLOB = b"mixed-study land bytes, synced"
MIXED_MARK_BLOB = b"mixed-study mark bytes, synced"


def _scan(*, content: bytes, source: str, source_ref: str, **kwargs) -> models.Scan:
    return models.Scan(
        content_hash=sha256_hex(content),
        size_bytes=len(content),
        source=source,
        source_ref=source_ref,
        **kwargs,
    )


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    """A tiny catalog exercising every containment path, plus a blob store that
    deliberately holds only *some* of the blobs (the live C3 situation)."""
    root = tmp_path_factory.mktemp("integrity")
    store = LocalBlobStore(root / "blobs")
    for blob in (PRESENT_BLOB, MIXED_LAND_BLOB, MIXED_MARK_BLOB):
        store.put(blob)

    engine = create_engine(f"sqlite:///{root / 'catalog.db'}")
    SQLModel.metadata.create_all(engine)
    # The manifest-mode dataset resolution matches Scan.source_ref against the
    # bundled manifest's file URLs — pin one scan to a real manifest entry.
    sample_manifest = load_manifest_by_name("hamby252-barrel1-sample")
    ids: dict[str, int] = {}
    with Session(engine) as session:
        # Bullet study (nbtrd): one land with a synced scan + an unsynced scan.
        bullets = models.Study(source="nbtrd", external_id="s-bullets", title="Bullets")
        session.add(bullets)
        session.commit()
        firearm = models.Firearm(study_id=bullets.id, caliber="9mm Luger", n_lands=6)
        session.add(firearm)
        session.commit()
        bullet = models.Bullet(firearm_id=firearm.id)
        session.add(bullet)
        session.commit()
        land = models.Land(bullet_id=bullet.id, position=1)
        session.add(land)
        session.commit()
        present_scan = _scan(
            content=PRESENT_BLOB,
            source="nbtrd",
            source_ref=sample_manifest.files[0].url,
            land_id=land.id,
            filename=sample_manifest.files[0].name,
        )
        missing_scan = _scan(
            content=MISSING_BLOB,
            source="nbtrd",
            source_ref="https://example.org/missing.x3p",
            land_id=land.id,
            filename="missing.x3p",
        )

        # Fadul-style cartridge study (csafe-isu) — matches the bundled
        # fadul-cartridge-cases manifest's study coordinates; blob not synced.
        fadul = models.Study(
            source="csafe-isu", external_id="fadul-cartridge-cases", title="Fadul"
        )
        session.add(fadul)
        session.commit()
        slide = models.Firearm(study_id=fadul.id, external_id="Slide1", brand="Glock")
        session.add(slide)
        session.commit()
        case = models.CartridgeCase(firearm_id=slide.id, external_id="Slide1-Case1")
        session.add(case)
        session.commit()
        mark = models.Mark(
            cartridge_case_id=case.id, external_id="Slide1-Case1-breech_face",
            mark_type="breech_face",
        )
        session.add(mark)
        session.commit()
        fadul_scan = _scan(
            content=FADUL_BLOB,
            source="csafe-isu",
            source_ref="https://raw.githubusercontent.com/CSAFE-ISU/x/Fadul 1-1.x3p",
            mark_id=mark.id,
            filename="Fadul 1-1.x3p",
        )

        # tmaRks-style toolmark study: 1-D profiles, blob not synced.
        tmarks = models.Study(source="tmarks", external_id="tmarks-screwdrivers", title="tmaRks")
        session.add(tmarks)
        session.commit()
        tool = models.Tool(study_id=tmarks.id, external_id="T01")
        session.add(tool)
        session.commit()
        toolmark = models.Toolmark(tool_id=tool.id, external_id="T01LA-F80-01", edge="T01LA")
        session.add(toolmark)
        session.commit()
        tmarks_scan = _scan(
            content=TMARKS_BLOB,
            source="tmarks",
            source_ref="https://github.com/heike/tmaRks",
            toolmark_id=toolmark.id,
            modality="profile_1d",
            filename="T01LA-F80-01",
        )

        # Mixed study: one firearm with a bullet-land scan AND a cartridge-mark scan.
        mixed = models.Study(source="nbtrd", external_id="s-mixed", title="Mixed")
        session.add(mixed)
        session.commit()
        mixed_firearm = models.Firearm(study_id=mixed.id, caliber=".45 Auto")
        session.add(mixed_firearm)
        session.commit()
        mixed_bullet = models.Bullet(firearm_id=mixed_firearm.id)
        session.add(mixed_bullet)
        session.commit()
        mixed_land = models.Land(bullet_id=mixed_bullet.id, position=1)
        mixed_case = models.CartridgeCase(firearm_id=mixed_firearm.id, external_id="MC1")
        session.add(mixed_land)
        session.add(mixed_case)
        session.commit()
        mixed_mark = models.Mark(
            cartridge_case_id=mixed_case.id, external_id="MC1-bf", mark_type="breech_face"
        )
        session.add(mixed_mark)
        session.commit()
        mixed_land_scan = _scan(
            content=MIXED_LAND_BLOB,
            source="nbtrd",
            source_ref="https://example.org/mixed-land.x3p",
            land_id=mixed_land.id,
        )
        mixed_mark_scan = _scan(
            content=MIXED_MARK_BLOB,
            source="nbtrd",
            source_ref="https://example.org/mixed-mark.x3p",
            mark_id=mixed_mark.id,
        )

        scans = {
            "present": present_scan,
            "missing": missing_scan,
            "fadul": fadul_scan,
            "tmarks": tmarks_scan,
            "mixed_land": mixed_land_scan,
            "mixed_mark": mixed_mark_scan,
        }
        for scan in scans.values():
            session.add(scan)
        session.commit()
        for key, scan in scans.items():
            session.refresh(scan)
            ids[key] = scan.id
        ids["study_bullets"] = bullets.id
        ids["study_fadul"] = fadul.id
        ids["study_tmarks"] = tmarks.id
        ids["study_mixed"] = mixed.id

    def _session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[deps.get_session] = _session_override
    app.dependency_overrides[deps.get_store] = lambda: store
    yield TestClient(app), ids
    app.dependency_overrides.pop(deps.get_session, None)
    app.dependency_overrides.pop(deps.get_store, None)


# --- blob_available: list field, facet, detail ------------------------------ #
def test_scan_list_reports_blob_availability(env):
    client, ids = env
    body = client.get("/scans", params={"limit": 200}).json()
    assert body["success"] is True
    by_id = {s["id"]: s for s in body["data"]}
    assert by_id[ids["present"]]["blob_available"] is True
    assert by_id[ids["missing"]]["blob_available"] is False
    assert by_id[ids["fadul"]]["blob_available"] is False
    assert by_id[ids["tmarks"]]["blob_available"] is False


def test_blob_available_facet_partitions_the_catalog(env):
    client, ids = env
    every = client.get("/scans").json()
    synced = client.get("/scans", params={"blob_available": "true"}).json()
    unsynced = client.get("/scans", params={"blob_available": "false"}).json()
    assert synced["meta"]["total"] + unsynced["meta"]["total"] == every["meta"]["total"]
    assert all(s["blob_available"] for s in synced["data"])
    assert all(not s["blob_available"] for s in unsynced["data"])
    assert ids["present"] in {s["id"] for s in synced["data"]}
    assert ids["missing"] in {s["id"] for s in unsynced["data"]}


def test_blob_available_facet_composes_with_other_facets(env):
    client, ids = env
    body = client.get(
        "/scans", params={"source": "tmarks", "blob_available": "false"}
    ).json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == ids["tmarks"]
    none = client.get(
        "/scans", params={"source": "tmarks", "blob_available": "true"}
    ).json()
    assert none["meta"]["total"] == 0
    assert none["data"] == []
    # ...including the join facets (caliber goes through Land→Bullet→Firearm).
    joined = client.get(
        "/scans", params={"caliber": "9mm Luger", "blob_available": "false"}
    ).json()
    assert joined["meta"]["total"] == 1
    assert joined["data"][0]["id"] == ids["missing"]


def test_scan_detail_reports_blob_availability(env):
    client, ids = env
    present = client.get(f"/scans/{ids['present']}").json()["data"]
    missing = client.get(f"/scans/{ids['missing']}").json()["data"]
    assert present["blob_available"] is True
    assert missing["blob_available"] is False


# --- the honest x3p 404 ------------------------------------------------------ #
def test_x3p_404_says_metadata_served_but_blob_pending(env):
    client, ids = env
    resp = client.get(f"/scans/{ids['missing']}/x3p")
    assert resp.status_code == 404
    err = resp.json()["error"]
    assert "metadata is served" in err
    assert "not yet in the public store" in err
    assert "blob_available" in err


def test_x3p_404_notes_profile_modality_for_toolmark_scans(env):
    client, ids = env
    err = client.get(f"/scans/{ids['tmarks']}/x3p").json()["error"]
    assert "1-D profile" in err
    assert "not an X3P" in err
    # ...and the note is absent for a plain x3p_3d scan.
    plain = client.get(f"/scans/{ids['missing']}/x3p").json()["error"]
    assert "1-D profile" not in plain


def test_x3p_present_blob_still_serves(env):
    client, ids = env
    resp = client.get(f"/scans/{ids['present']}/x3p")
    assert resp.status_code == 200
    assert sha256_hex(resp.content) == sha256_hex(PRESENT_BLOB)


# --- the study facet across all three mark families -------------------------- #
def test_study_facet_returns_cartridge_scans(env):
    # Previously: ?study_id=<Fadul> silently returned total 0.
    client, ids = env
    body = client.get("/scans", params={"study_id": ids["study_fadul"]}).json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == ids["fadul"]
    assert body["data"][0]["mark_id"] is not None


def test_study_facet_returns_toolmark_scans(env):
    # Previously: ?study_id=<tmaRks> silently returned total 0.
    client, ids = env
    body = client.get("/scans", params={"study_id": ids["study_tmarks"]}).json()
    assert body["meta"]["total"] == 1
    assert body["data"][0]["id"] == ids["tmarks"]
    assert body["data"][0]["toolmark_id"] is not None
    assert body["data"][0]["modality"] == "profile_1d"


def test_study_facet_mixed_study_returns_both_kinds(env):
    # Previously: a mixed study returned only its bullet-land scans.
    client, ids = env
    body = client.get("/scans", params={"study_id": ids["study_mixed"]}).json()
    assert body["meta"]["total"] == 2
    returned = {s["id"] for s in body["data"]}
    assert returned == {ids["mixed_land"], ids["mixed_mark"]}


def test_study_facet_still_composes_with_firearm_facets(env):
    client, ids = env
    body = client.get(
        "/scans", params={"study_id": ids["study_bullets"], "caliber": "9mm Luger"}
    ).json()
    assert body["meta"]["total"] == 2  # the two land scans of the bullet study
    assert {s["id"] for s in body["data"]} == {ids["present"], ids["missing"]}


# --- dataset resolution ------------------------------------------------------ #
def test_dataset_list_includes_n_resolved(env):
    client, _ = env
    body = client.get("/datasets").json()
    assert body["success"] is True
    by_name = {d["name"]: d for d in body["data"]}
    assert all("n_resolved" in d for d in body["data"])
    # A huge, unpinned manifest must not read as 15k pinned files.
    assert by_name["lapd"]["n_files"] == 15027
    assert by_name["lapd"]["n_resolved"] == 0
    # The pinned bullet scan resolves its manifest entry.
    assert by_name["hamby252-barrel1-sample"]["n_resolved"] == 1
    # Discover-at-ingest manifest: counts come from the catalog.
    assert by_name["fadul-cartridge-cases"]["n_files"] == 1
    assert by_name["fadul-cartridge-cases"]["n_resolved"] == 1


def test_dataset_detail_resolves_fadul_from_the_catalog(env):
    # Previously: 200 with n_files 0 / files [] while the scans existed.
    client, ids = env
    data = client.get("/datasets/fadul-cartridge-cases").json()["data"]
    assert data["resolution"] == "catalog"
    assert data["n_files"] == data["n_resolved"] == 1
    assert data["note"] and "ingest" in data["note"]
    (entry,) = data["files"]
    assert entry["scan_id"] == ids["fadul"]
    assert entry["name"] == "Fadul 1-1.x3p"
    assert len(entry["content_hash"]) == 64


def test_dataset_detail_flags_unresolved_as_pending(env):
    # A discover-at-ingest manifest with nothing ingested is honestly flagged.
    client, _ = env
    data = client.get("/datasets/weller-cartridge-cases").json()["data"]
    assert data["resolution"] == "pending"
    assert data["n_files"] == data["n_resolved"] == 0
    assert data["files"] == []
    assert data["note"] and "nothing to pin" in data["note"]


def test_dataset_detail_manifest_mode_unchanged(env):
    client, ids = env
    data = client.get("/datasets/hamby252-barrel1-sample").json()["data"]
    assert data["resolution"] == "manifest"
    assert data["note"] is None
    assert data["n_files"] == 12
    assert data["n_resolved"] == 1
    pinned = [f for f in data["files"] if f["content_hash"]]
    assert len(pinned) == 1
    assert pinned[0]["scan_id"] == ids["present"]


# --- self-documenting OpenAPI ------------------------------------------------ #
def test_openapi_documents_per_source_licensing(env):
    client, _ = env
    desc = client.get("/openapi.json").json()["info"]["description"]
    for token in ("public domain", "NBTRD", "CC BY 4.0", "MIT", "cartridge-cases"):
        assert token in desc, f"app description is missing {token!r}"


def test_openapi_source_facet_lists_every_source(env):
    client, _ = env
    spec = client.get("/openapi.json").json()
    params = {p["name"]: p for p in spec["paths"]["/scans"]["get"]["parameters"]}
    for source in models.SOURCES:
        assert source in params["source"]["description"]
    assert "blob_available" in params
    assert "store" in params["blob_available"]["description"]