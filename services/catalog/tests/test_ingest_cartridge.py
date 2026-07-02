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


def test_cartridge_directory_labeling_builds_hierarchy(session, tmp_path):
    """Weller-style recursive harvests: the slide DIRECTORY is the source
    (pre-registration §4.2), taking precedence over the {slide}-{case} filename
    regex — which would otherwise mislabel every ``TWxx-NN.x3p`` name."""
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("weller-cartridge-cases")
    names = ["TW01/TW01-01.x3p", "TW01/TW01-02.x3p", "TW02/TW02-01.x3p"]
    blobs = {n: _x3p_bytes(float(i)) for i, n in enumerate(names)}
    src = FakeSource(_files(names), lambda rf: blobs[rf.name])

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats == {"files": 3, "ingested": 3, "already_present": 0, "skipped_no_match": 0}
    # SOURCE identity is the TW directory: 2 firearms, named exactly by directory
    firearms = session.exec(select(models.Firearm)).all()
    assert sorted(f.external_id for f in firearms) == ["TW01", "TW02"]
    # ...NOT the filename-regex labels ("TW01-01.x3p" matches the {slide}-{case}
    # regex as slide 1 — directory precedence must win)
    assert not any(f.external_id.startswith("Slide") for f in firearms)
    assert all(f.brand == "Ruger" and f.model == "P95" for f in firearms)
    assert len(session.exec(select(models.CartridgeCase)).all()) == 3
    marks = session.exec(select(models.Mark)).all()
    assert len(marks) == 3
    assert all(mk.mark_type == "breech_face" for mk in marks)
    scans = session.exec(select(models.Scan)).all()
    assert len(scans) == 3
    # the scan keeps its directory-relative filename and resolves to its slide
    s = next(s for s in scans if s.filename == "TW01/TW01-02.x3p")
    assert s.mark.cartridge_case.firearm.external_id == "TW01"
    assert s.mark.cartridge_case.external_id == "TW01-02"
    assert s.mark.cartridge_case.label == "TW01-02"
    assert s.mark.external_id == "TW01-02-breech_face"


def test_cartridge_directory_labeling_skips_unattributable(session, tmp_path):
    """A scan not attributable to EXACTLY ONE slide directory is skipped and
    counted (pre-registration §5.5 rule 2) — never guessed at."""
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("weller-cartridge-cases")
    names = [
        "TW01/TW01-01.x3p",  # attributable: exactly one slide directory
        "TW01/nested/TW01-99.x3p",  # two directory components -> unattributable
        "/TW03-01.x3p",  # empty directory component -> unattributable
        "stray.x3p",  # flat, no {slide}-{case} match -> unattributable
    ]
    blobs = {n: _x3p_bytes(float(i)) for i, n in enumerate(names)}
    src = FakeSource(_files(names), lambda rf: blobs[rf.name])

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats == {"files": 4, "ingested": 1, "already_present": 0, "skipped_no_match": 3}
    firearms = session.exec(select(models.Firearm)).all()
    assert [f.external_id for f in firearms] == ["TW01"]
    assert len(session.exec(select(models.Scan)).all()) == 1


def test_cartridge_directory_labeling_dedups_identical_content(session, tmp_path):
    """Content-hash dedup (pre-registration §5.5 rule 3) also holds for
    directory-labeled scans: one blob, one Scan row, first occurrence kept."""
    store = LocalBlobStore(tmp_path / "blobs")
    manifest = load_manifest("weller-cartridge-cases")
    names = ["TW01/TW01-01.x3p", "TW02/TW02-01.x3p"]
    src = FakeSource(_files(names), lambda rf: _x3p_bytes(0.0))  # identical bytes

    stats = ingest_manifest(session, store, manifest, source=src)

    assert stats["files"] == 2 and stats["ingested"] == 2
    assert len(session.exec(select(models.Scan)).all()) == 1
    assert store.count() == 1
    # both slides' cases + marks still exist (labeling is independent of dedup)
    assert len(session.exec(select(models.Firearm)).all()) == 2
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
