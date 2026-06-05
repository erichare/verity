"""Offline ingest tests: real X3P bytes through the full pipeline (validated by
verity-x3p), with an injected source so no network is touched."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlmodel import Session, create_engine, select

pytest.importorskip("yaml")
verity_x3p = pytest.importorskip("verity_x3p")
np = pytest.importorskip("numpy")

from verity_catalog import models  # noqa: E402
from verity_catalog.db import create_all  # noqa: E402
from verity_catalog.harvest.base import RemoteFile  # noqa: E402
from verity_catalog.ingest import ingest_manifest, load_manifest  # noqa: E402
from verity_catalog.store import LocalBlobStore  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "csafe-logo.x3p"


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    create_all(engine)
    with Session(engine) as s:
        yield s


class FakeSource:
    """Returns canned bytes per file — no network."""

    def __init__(self, files, data_for):
        self._files = files
        self._data_for = data_for

    def discover(self):
        return list(self._files)

    def fetch(self, remote):
        return self._data_for(remote)


def _make_x3p_bytes(offset: float) -> bytes:
    """Write a small, valid, *distinct* X3P via verity-x3p and return its bytes."""
    arr = np.arange(12, dtype=float).reshape(3, 4) + offset
    surface = verity_x3p.Surface(arr, increment_x=1e-6, increment_y=1e-6)
    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        verity_x3p.write_x3p(surface, path)
        return Path(path).read_bytes()
    finally:
        Path(path).unlink()


def test_ingest_single_real_file(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("hamby252-barrel1-sample")
    files = [RemoteFile(name="Hamby252_Barrel1_Bullet1_Land1.x3p", url="https://x/1")]
    src = FakeSource(files, lambda rf: FIXTURE.read_bytes())

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats == {"files": 1, "ingested": 1, "already_present": 0, "skipped_no_lea": 0}
    scans = session.exec(select(models.Scan)).all()
    assert len(scans) == 1
    scan = scans[0]
    assert scan.modality == "x3p_3d"
    assert scan.content_hash and store.exists(scan.content_hash)
    assert scan.size_bytes == FIXTURE.stat().st_size
    # csafe-logo: 6.45e-7 m -> 0.645 µm
    assert abs(scan.lateral_resolution_x - 0.645) < 1e-3
    meta = json.loads(scan.x3p_meta_json)
    assert (meta["nx"], meta["ny"]) == (741, 419)
    assert meta["z_type"] == "D"
    # hierarchy + firearm defaults applied
    assert scan.land.position == 1
    assert scan.land.bullet.firearm.external_id == "Barrel1"
    assert scan.land.bullet.firearm.caliber == "9mm Luger"


def test_ingest_builds_hierarchy_and_dedups(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("hamby252-barrel1-sample")
    files = [RemoteFile(name=f.name, url=f.url) for f in manifest.files]
    src = FakeSource(files, lambda rf: FIXTURE.read_bytes())  # identical bytes

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats["files"] == 12 and stats["ingested"] == 12
    assert len(session.exec(select(models.Firearm)).all()) == 1
    assert len(session.exec(select(models.Bullet)).all()) == 2
    assert len(session.exec(select(models.Land)).all()) == 12
    # identical content dedups to ONE scan and ONE blob
    assert len(session.exec(select(models.Scan)).all()) == 1
    assert store.count() == 1
    # KM: all lands resolve to the same firearm
    firearm_ids = {ld.bullet.firearm_id for ld in session.exec(select(models.Land)).all()}
    assert len(firearm_ids) == 1


def test_distinct_files_create_distinct_scans(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("hamby252-barrel1-sample")
    chosen = manifest.files[:3]
    blobs = {f.name: _make_x3p_bytes(float(i)) for i, f in enumerate(chosen)}
    files = [RemoteFile(name=f.name, url=f.url) for f in chosen]
    src = FakeSource(files, lambda rf: blobs[rf.name])

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats["ingested"] == 3
    assert len(session.exec(select(models.Scan)).all()) == 3
    assert store.count() == 3


def test_ingest_is_idempotent(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("hamby252-barrel1-sample")
    files = [RemoteFile(name=manifest.files[0].name, url=manifest.files[0].url)]
    src = FakeSource(files, lambda rf: FIXTURE.read_bytes())

    stats1 = ingest_manifest(session, store, manifest, source=src)
    stats2 = ingest_manifest(session, store, manifest, source=src)  # run again

    assert stats1["ingested"] == 1
    # second run skips the already-present scan without re-downloading
    assert stats2["ingested"] == 0 and stats2["already_present"] == 1
    assert len(session.exec(select(models.Study)).all()) == 1
    assert len(session.exec(select(models.Firearm)).all()) == 1
    assert len(session.exec(select(models.Land)).all()) == 1
    assert len(session.exec(select(models.Scan)).all()) == 1


def test_corrupt_x3p_is_rejected(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("hamby252-barrel1-sample")
    bad = bytearray(FIXTURE.read_bytes())
    bad[len(bad) // 2] ^= 0xFF  # break the data so the MD5 check fails
    files = [RemoteFile(name="Hamby252_Barrel1_Bullet1_Land1.x3p", url="https://x/1")]
    src = FakeSource(files, lambda rf: bytes(bad))

    # Corruption is rejected either by the zip CRC (OSError) or the X3P MD5
    # (ValueError), depending on where the flipped byte lands.
    with pytest.raises((ValueError, OSError)):
        ingest_manifest(session, store, manifest, source=src)
