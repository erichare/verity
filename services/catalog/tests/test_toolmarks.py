"""Offline toolmark-ingest tests: 1-D screwdriver profiles through the
Study -> Tool -> Toolmark -> Scan path, from a synthetic CSV cache (no R, no
network), with content-hash dedup and idempotency."""

import array

import pytest
from sqlmodel import Session, create_engine, select

from verity_catalog import models
from verity_catalog.db import create_all
from verity_catalog.store import LocalBlobStore
from verity_catalog.toolmarks import (
    _serialize_profile,
    ingest_tmaRks,
    parse_tmarks_tid,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    create_all(engine)
    with Session(engine) as s:
        yield s


def _write_cache(cache_dir, rows):
    """rows = list of (TID, [values]) -> a tmaRks-style long CSV cache."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    lines = ['"TID","value"']
    for tid, values in rows:
        lines += [f'"{tid}",{v}' for v in values]
    (cache_dir / "toolmarks_long.csv").write_text("\n".join(lines) + "\n")


def test_parse_tmarks_tid():
    assert parse_tmarks_tid("T01LA-F60-01") == ("T01", "T01LA", "A")
    assert parse_tmarks_tid("T20SB-F80-08") == ("T20", "T20SB", "B")
    assert parse_tmarks_tid("garbage") is None


def test_serialize_profile_roundtrips_and_is_deterministic():
    values = [0.5, -1.25, 3.0, 42.0]
    blob = _serialize_profile(values)
    assert len(blob) == len(values) * 8  # float64
    back = array.array("d")
    back.frombytes(blob)
    assert list(back) == values
    assert _serialize_profile(values) == blob  # same input -> same bytes


def test_ingest_builds_toolmark_hierarchy(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    cache = tmp_path / "tmaRks"
    _write_cache(
        cache,
        [
            ("T01LA-F60-01", [1.0, 2.0, 3.0]),
            ("T01LA-F60-02", [1.1, 2.1, 3.1]),  # same edge T01LA, different mark
            ("T01SB-F80-01", [4.0, 5.0, 6.0]),  # same tool T01, other edge
            ("T07SA-F70-03", [7.0, 8.0, 9.0]),  # different tool
        ],
    )

    stats = ingest_tmaRks(session, store, cache_dir=cache)

    assert stats == {"marks": 4, "ingested": 4, "already_present": 0, "skipped": 0}
    study = session.exec(select(models.Study)).one()
    assert study.source == "tmarks"
    assert study.consecutively_manufactured is True
    # 2 tools (T01, T07), 4 marks, 4 profile scans
    assert {t.external_id for t in session.exec(select(models.Tool)).all()} == {"T01", "T07"}
    toolmarks = session.exec(select(models.Toolmark)).all()
    assert len(toolmarks) == 4
    scans = session.exec(select(models.Scan)).all()
    assert len(scans) == 4
    # toolmark scans attach via toolmark_id only (never land/mark)
    assert all(
        s.toolmark_id is not None and s.land_id is None and s.mark_id is None for s in scans
    )
    assert all(s.modality == "profile_1d" for s in scans)
    # one mark resolves up to its edge + tool
    tm = next(t for t in toolmarks if t.external_id == "T01LA-F60-01")
    assert tm.edge == "T01LA" and tm.side == "A"
    assert tm.tool.external_id == "T01"
    assert store.exists(next(s for s in scans if s.toolmark_id == tm.id).content_hash)


def test_ingest_dedups_identical_profiles(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    cache = tmp_path / "tmaRks"
    _write_cache(
        cache,
        [
            ("T01LA-F60-01", [1.0, 2.0, 3.0]),
            ("T09SB-F80-07", [1.0, 2.0, 3.0]),  # byte-identical profile -> dedups
        ],
    )

    stats = ingest_tmaRks(session, store, cache_dir=cache)

    assert stats["marks"] == 2
    assert stats["ingested"] == 1 and stats["already_present"] == 1
    assert len(session.exec(select(models.Scan)).all()) == 1
    assert store.count() == 1


def test_ingest_is_idempotent(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    cache = tmp_path / "tmaRks"
    _write_cache(cache, [("T01LA-F60-01", [1.0, 2.0, 3.0])])

    first = ingest_tmaRks(session, store, cache_dir=cache)
    second = ingest_tmaRks(session, store, cache_dir=cache)  # re-run

    assert first["ingested"] == 1
    assert second["ingested"] == 0 and second["already_present"] == 1
    assert len(session.exec(select(models.Study)).all()) == 1
    assert len(session.exec(select(models.Tool)).all()) == 1
    assert len(session.exec(select(models.Toolmark)).all()) == 1
    assert len(session.exec(select(models.Scan)).all()) == 1


def test_ingest_missing_cache_raises(session, tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    with pytest.raises(FileNotFoundError, match="tmaRks"):
        ingest_tmaRks(session, store, cache_dir=tmp_path / "nope")
