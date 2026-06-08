"""migrate-db plumbing: row-copy preserves ids + content hashes and is idempotent.

Exercised SQLite -> SQLite (a throwaway file DB) so no Postgres is required; the
copy logic is dialect-agnostic. sync_blobs is covered against the fake S3 store."""

from __future__ import annotations

import pytest
from sqlmodel import Session, create_engine, select

from verity_catalog import models
from verity_catalog.db import create_all
from verity_catalog.migrate import migrate_db, sync_blobs
from verity_catalog.store import LocalBlobStore, sha256_hex


def _seed(engine) -> None:
    create_all(engine)
    with Session(engine) as s:
        study = models.Study(source="nbtrd", external_id="g1", title="S")
        s.add(study)
        s.commit()
        s.refresh(study)
        firearm = models.Firearm(study_id=study.id, brand="Ruger", caliber="9mm Luger", n_lands=6)
        s.add(firearm)
        s.commit()
        s.refresh(firearm)
        bullet = models.Bullet(firearm_id=firearm.id)
        s.add(bullet)
        s.commit()
        s.refresh(bullet)
        land = models.Land(bullet_id=bullet.id, position=1)
        s.add(land)
        s.commit()
        s.refresh(land)
        s.add(
            models.Scan(
                land_id=land.id,
                modality="x3p_3d",
                content_hash="a" * 64,
                size_bytes=10,
                source="nbtrd",
                source_ref="https://x/1",
            )
        )
        s.commit()


def test_migrate_db_preserves_ids_and_hashes(tmp_path):
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    _seed(src)
    target_url = f"sqlite:///{tmp_path / 'dst.db'}"

    inserted = migrate_db(target_url, source_engine=src)
    assert inserted["Study"] == 1
    assert inserted["Scan"] == 1

    dst = create_engine(target_url)
    with Session(dst) as s:
        scans = s.exec(select(models.Scan)).all()
        assert len(scans) == 1
        assert scans[0].id == 1
        assert scans[0].content_hash == "a" * 64
        # FK preserved: scan -> land -> bullet -> firearm caliber
        assert scans[0].land.bullet.firearm.caliber == "9mm Luger"


def test_migrate_db_is_idempotent(tmp_path):
    src = create_engine(f"sqlite:///{tmp_path / 'src.db'}")
    _seed(src)
    target_url = f"sqlite:///{tmp_path / 'dst.db'}"

    migrate_db(target_url, source_engine=src)
    second = migrate_db(target_url, source_engine=src)  # re-run
    assert sum(second.values()) == 0  # nothing new inserted

    dst = create_engine(target_url)
    with Session(dst) as s:
        assert len(s.exec(select(models.Scan)).all()) == 1
        assert len(s.exec(select(models.Study)).all()) == 1


def test_sync_blobs_uploads_and_verifies(tmp_path):
    moto = pytest.importorskip("moto")
    import boto3

    from verity_catalog.store_s3 import S3BlobStore

    source = LocalBlobStore(tmp_path / "blobs")
    h1 = source.put(b"scan one")
    h2 = source.put(b"scan two")

    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="verity-sync")
        target = S3BlobStore("verity-sync", client=client)

        stats = sync_blobs(target, source_store=source)
        assert stats["total"] == 2
        assert stats["uploaded"] == 2
        assert stats["verified"] == 2
        assert target.exists(h1) and target.exists(h2)
        assert sha256_hex(target.get(h1)) == h1

        # re-run: idempotent, nothing re-uploaded
        again = sync_blobs(target, source_store=source)
        assert again["uploaded"] == 0
        assert again["already_present"] == 2
