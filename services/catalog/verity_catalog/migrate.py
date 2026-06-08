"""Go-live data movers: copy the local catalog to Postgres and the local blobs
to S3/R2.

Both operations are **idempotent** and **content-preserving**:

- :func:`migrate_db` streams every row from the source (SQLite) catalog into the
  target (Postgres) database table-by-table in FK-safe order, preserving primary
  keys and ``content_hash`` exactly. Re-running skips rows whose primary key is
  already present, so an interrupted migration can simply be re-run.
- :func:`sync_blobs` uploads every local blob to the configured object store and
  verifies each one reads back with the identical SHA-256 — the same self-checking
  invariant the content-addressed store is built on.

Neither needs the heavy science stack; they operate purely on the catalog schema
and the blob bytes.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine, select

from . import models
from .db import engine as local_engine
from .store import BlobStore, LocalBlobStore, sha256_hex

# FK-safe insertion order: parents before children (mirrors the containment
# hierarchy; Instrument is referenced by Scan so it precedes it).
MIGRATION_ORDER = (
    models.Study,
    models.Firearm,
    models.Bullet,
    models.CartridgeCase,
    models.Land,
    models.Mark,
    models.Instrument,
    models.Scan,
    models.ScanTrace,
    models.PairDiagnostic,
)


def _existing_ids(session: Session, model: type[SQLModel]) -> set[int]:
    """Primary-key ids already present in ``session``'s table for ``model``."""
    return set(session.exec(select(model.id)).all())  # type: ignore[attr-defined]


def migrate_db(
    target_url: str,
    *,
    source_engine: Engine | None = None,
    create_schema: bool = True,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, int]:
    """Copy every row from the source catalog into ``target_url``.

    Primary keys (and therefore all foreign keys) are preserved, so the target is
    a faithful clone. Idempotent: rows whose id already exists in the target are
    skipped. Returns a per-table count of rows inserted.

    ``create_schema`` runs ``create_all`` on the target first (safe to leave on;
    for the canonical path run ``alembic upgrade head`` against the target and
    pass ``create_schema=False``)."""
    src = source_engine or local_engine
    dst = create_engine(target_url)
    if create_schema:
        SQLModel.metadata.create_all(dst)

    inserted: dict[str, int] = {}
    with Session(src) as src_session, Session(dst) as dst_session:
        for model in MIGRATION_ORDER:
            name = model.__name__
            rows = src_session.exec(select(model)).all()
            present = _existing_ids(dst_session, model)
            new_count = 0
            for row in rows:
                if row.id in present:  # type: ignore[attr-defined]
                    continue
                # Detach from the source session and re-add to the target with the
                # same PK. model_dump() copies scalar columns only (no relationships).
                dst_session.add(model(**row.model_dump()))
                new_count += 1
            dst_session.commit()
            inserted[name] = new_count
            if on_progress:
                on_progress(name, new_count, len(rows))

    # Postgres sequences don't advance when explicit ids are inserted; bump each
    # table's id sequence past the max so future inserts don't collide.
    if dst.dialect.name == "postgresql":
        _reset_pg_sequences(dst)
    return inserted


def _reset_pg_sequences(dst: Engine) -> None:
    """Advance each table's id sequence past the largest inserted id (Postgres)."""
    from sqlalchemy import text

    with Session(dst) as session:
        for model in MIGRATION_ORDER:
            table = model.__tablename__  # type: ignore[attr-defined]
            max_id = session.exec(select(func.max(model.id))).one()  # type: ignore[attr-defined]
            if max_id:
                session.exec(
                    text(
                        "SELECT setval(pg_get_serial_sequence(:t, 'id'), :v, true)"
                    ).bindparams(t=table, v=max_id)
                )
        session.commit()


def sync_blobs(
    target_store: BlobStore,
    *,
    source_store: BlobStore | None = None,
    source_root=None,
    verify: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, int]:
    """Upload every blob from the local store to ``target_store``.

    Each upload is verified by reading the object back and re-hashing it; a
    mismatch raises ``RuntimeError`` (the content-addressed invariant must hold on
    the destination too). Idempotent: blobs already present at the target are
    skipped. Returns ``{uploaded, already_present, verified, total}``."""
    from .config import get_settings

    if source_store is None:
        root = source_root if source_root is not None else get_settings().blob_store_path
        source_store = LocalBlobStore(root)
    if not isinstance(source_store, LocalBlobStore):
        raise TypeError("sync_blobs reads from a LocalBlobStore source")

    hashes = sorted(p.stem for p in source_store.root.rglob("*.bin"))
    stats = {"uploaded": 0, "already_present": 0, "verified": 0, "total": len(hashes)}
    for index, content_hash in enumerate(hashes, start=1):
        if target_store.exists(content_hash):
            stats["already_present"] += 1
        else:
            data = source_store.get(content_hash)
            target_store.put(data)
            stats["uploaded"] += 1
            if verify:
                roundtrip = target_store.get(content_hash)
                if sha256_hex(roundtrip) != content_hash:
                    raise RuntimeError(
                        f"verification failed for {content_hash}: target readback hash differs"
                    )
                stats["verified"] += 1
        if on_progress:
            on_progress(index, len(hashes), content_hash)
    return stats
