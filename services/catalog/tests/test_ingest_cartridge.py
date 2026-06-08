"""Offline cartridge ingest tests: real X3P bytes through the cartridge pipeline
(Firearm(Slide) -> CartridgeCase -> Mark(breech_face) -> Scan), validated by
verity-x3p, with an injected source so no network is touched."""

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


def _x3p_bytes(offset: float) -> bytes:
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


def _files(names):
    return [RemoteFile(name=n, url=f"https://raw/{n}") for n in names]


def test_cartridge_builds_hierarchy(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("fadul-cartridge-cases")
    names = ["Fadul 1-1.x3p", "Fadul 1-2.x3p", "Fadul 2-1.x3p"]  # 2 slides, 3 cases
    blobs = {n: _x3p_bytes(float(i)) for i, n in enumerate(names)}
    src = FakeSource(_files(names), lambda rf: blobs[rf.name])

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats == {"files": 3, "ingested": 3, "already_present": 0, "skipped_no_match": 0}
    # study provenance carried from the manifest
    study = session.exec(select(models.Study)).one()
    assert study.source == "csafe-isu"
    assert study.consecutively_manufactured is True
    assert study.creator == "CSAFE-ISU / Fadul et al."
    assert "CC-BY 4.0" in study.references
    # hierarchy: 2 slides, 3 cases, 3 breech-face marks, 3 scans
    assert len(session.exec(select(models.Firearm)).all()) == 2
    assert len(session.exec(select(models.CartridgeCase)).all()) == 3
    marks = session.exec(select(models.Mark)).all()
    assert len(marks) == 3
    assert all(mk.mark_type == "breech_face" for mk in marks)
    scans = session.exec(select(models.Scan)).all()
    assert len(scans) == 3
    # cartridge scans attach via mark_id (never land_id)
    assert all(s.mark_id is not None and s.land_id is None for s in scans)
    # one scan resolves all the way up to slide 1, brand Glock
    s11 = next(s for s in scans if s.filename == "Fadul 1-1.x3p")
    assert s11.mark.cartridge_case.firearm.external_id == "Slide1"
    assert s11.mark.cartridge_case.firearm.brand == "Glock"
    assert s11.mark.cartridge_case.label == "Fadul 1-1"
    assert s11.content_hash and store.exists(s11.content_hash)
    assert abs(s11.lateral_resolution_x - 1.0) < 1e-6  # 1e-6 m -> 1 µm


def test_cartridge_skips_questioned_and_dedups(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("fadul-cartridge-cases")
    names = ["Fadul 1-1.x3p", "Fadul 1-2.x3p", "Fadul A.x3p"]  # A = questioned (lettered)
    src = FakeSource(_files(names), lambda rf: _x3p_bytes(0.0))  # identical bytes -> dedup

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats["files"] == 3
    assert stats["skipped_no_match"] == 1  # "Fadul A.x3p" has no known source slide
    assert stats["ingested"] == 2
    # identical content dedups to ONE scan + ONE blob...
    assert len(session.exec(select(models.Scan)).all()) == 1
    assert store.count() == 1
    # ...but both known cases + marks are still created (a KM pair under slide 1)
    assert len(session.exec(select(models.Firearm)).all()) == 1
    assert len(session.exec(select(models.CartridgeCase)).all()) == 2
    assert len(session.exec(select(models.Mark)).all()) == 2


def test_cartridge_ingest_is_idempotent(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("fadul-cartridge-cases")
    src = FakeSource(_files(["Fadul 1-1.x3p"]), lambda rf: _x3p_bytes(0.0))

    stats1 = ingest_manifest(session, store, manifest, source=src)
    stats2 = ingest_manifest(session, store, manifest, source=src)  # run again

    assert stats1["ingested"] == 1
    # second run skips the already-present scan without re-downloading
    assert stats2["ingested"] == 0 and stats2["already_present"] == 1
    assert len(session.exec(select(models.Study)).all()) == 1
    assert len(session.exec(select(models.Firearm)).all()) == 1
    assert len(session.exec(select(models.CartridgeCase)).all()) == 1
    assert len(session.exec(select(models.Mark)).all()) == 1
    assert len(session.exec(select(models.Scan)).all()) == 1
