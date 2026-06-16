"""The ``verity-catalog`` command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer
from sqlalchemy import func
from sqlmodel import Session, select

from . import models
from .config import get_settings
from .db import create_all, engine
from .store import get_store

app = typer.Typer(help="Verity data catalog", no_args_is_help=True)


@app.command("init-db")
def init_db() -> None:
    """Create the catalog schema (local-first; use Alembic for migrations)."""
    create_all()
    typer.echo(f"schema created at {get_settings().database_url}")


@app.command()
def info() -> None:
    """Show configuration and current catalog/store counts."""
    settings = get_settings()
    store = get_store(settings)
    typer.echo(f"database_url : {settings.database_url}")
    typer.echo(f"blob_store   : {settings.blob_store_backend} @ {settings.blob_store_path}")
    typer.echo("counts:")
    with Session(engine) as session:
        for model in models.ALL_MODELS:
            count = session.exec(select(func.count()).select_from(model)).one()
            typer.echo(f"  {model.__name__:<14} {count}")
    typer.echo(f"  {'blobs':<14} {store.count()}")


@app.command()
def ingest(
    manifest: str = typer.Argument(..., help="Manifest name (see 'manifests') or path to a .yaml"),
    limit: int | None = typer.Option(None, help="Max number of files to ingest"),
) -> None:
    """Ingest a dataset manifest: fetch, validate (verity-x3p), hash, catalog."""
    from .ingest import ingest_manifest, load_manifest
    from .store import get_store

    manifest_obj = load_manifest(manifest)
    store = get_store()

    def _progress(index: int, total: int, name: str) -> None:
        typer.echo(f"  [{index}/{total}] {name}")

    with Session(engine) as session:
        stats = ingest_manifest(session, store, manifest_obj, limit=limit, on_progress=_progress)
    typer.echo(f"ingested '{manifest_obj.name}': {stats}")


@app.command("ingest-toolmarks")
def ingest_toolmarks_cmd(
    dataset: str = typer.Argument("tmarks", help="Toolmark dataset (currently: tmarks)"),
    cache_dir: Path | None = typer.Option(
        None, help="Profile cache dir (default ~/.cache/verity/tmaRks)"
    ),
) -> None:
    """Ingest 1-D toolmark profiles (the tmaRks screwdriver set) as profile_1d scans."""
    from .toolmarks import TMARKS_CACHE, ingest_tmaRks

    if dataset != "tmarks":
        raise typer.BadParameter(f"unknown toolmark dataset: {dataset!r} (only 'tmarks')")
    store = get_store()

    def _progress(index: int, total: int, tid: str) -> None:
        if index % 50 == 0 or index == total:
            typer.echo(f"  [{index}/{total}] {tid}")

    with Session(engine) as session:
        stats = ingest_tmaRks(
            session, store, cache_dir=cache_dir or TMARKS_CACHE, on_progress=_progress
        )
    typer.echo(f"ingested tmaRks toolmarks: {stats}")


@app.command("ingest-virtual-kits")
def ingest_virtual_kits_cmd(
    cache_dir: Path | None = typer.Option(
        None, help="Dataset cache dir (default ~/.cache/verity/virtual-kits)"
    ),
    download: bool = typer.Option(True, help="Download missing files from figshare first (~18 GB)"),
    limit: int | None = typer.Option(None, help="Max number of scans to ingest"),
    skip_invalid: bool = typer.Option(
        False, help="Skip (and count) scans that fail validation instead of aborting"
    ),
) -> None:
    """Ingest the CSAFE/ISU multi-instrument virtual-kits dataset (bullets +
    cartridge cases on Evofinder/Quantum/Cadre TopMatch; figshare 30854414)."""
    from . import virtual_kits as vk

    cache = cache_dir or vk.CACHE_DIR
    store = get_store()

    if download:

        def _dl(name: str, received: int, total: int | None) -> None:
            pct = f"{100 * received / total:5.1f}%" if total else "  ?  "
            typer.echo(f"\r  downloading {name:<26} {pct} ({received >> 20} MiB)", nl=False)

        typer.echo(f"downloading dataset into {cache} ...")
        vk.download_dataset(cache, on_progress=_dl)
        typer.echo("")

    def _progress(index: int, total: int, name: str) -> None:
        if index % 25 == 0 or index == total:
            typer.echo(f"  [{index}/{total}] {name}")

    with Session(engine) as session:
        stats = vk.ingest_virtual_kits(
            session,
            store,
            cache_dir=cache,
            limit=limit,
            continue_on_error=skip_invalid,
            on_progress=_progress,
        )
    typer.echo(f"ingested virtual-kits: {stats}")


@app.command("manifests")
def list_manifests() -> None:
    """List the bundled dataset manifests."""
    from .ingest import MANIFEST_DIR

    for path in sorted(MANIFEST_DIR.glob("*.yaml")):
        typer.echo(path.stem)


@app.command("migrate-db")
def migrate_db_cmd(
    to: str = typer.Option(..., "--to", help="Target DB URL, e.g. postgresql://user:pass@host/db"),
    create_schema: bool = typer.Option(
        True, help="Create tables on the target first (disable if you ran alembic upgrade head)"
    ),
) -> None:
    """Copy the local catalog into a target DB (Postgres), preserving ids +
    content hashes. Idempotent — re-run to resume."""
    from .migrate import migrate_db

    typer.echo(f"migrating catalog -> {to}")

    def _progress(table: str, inserted: int, total: int) -> None:
        typer.echo(f"  {table:<16} +{inserted} (of {total})")

    inserted = migrate_db(to, create_schema=create_schema, on_progress=_progress)
    typer.echo(f"done: {sum(inserted.values())} rows inserted")


@app.command("sync-blobs")
def sync_blobs_cmd(
    to: str = typer.Option("s3", "--to", help="Target backend (currently only 's3')"),
) -> None:
    """Upload every local blob to the configured S3/R2 backend, verifying each
    reads back with the same SHA-256. Idempotent — re-run to resume."""
    if to != "s3":
        raise typer.BadParameter("only --to s3 is supported")
    from .migrate import sync_blobs
    from .store import LocalBlobStore, _s3_store

    settings = get_settings()
    target = _s3_store(settings, settings.blob_store_bucket)
    source = LocalBlobStore(settings.blob_store_path)
    typer.echo(f"syncing blobs {settings.blob_store_path} -> s3://{settings.blob_store_bucket}")

    def _progress(index: int, total: int, content_hash: str) -> None:
        typer.echo(f"  [{index}/{total}] {content_hash[:12]}…")

    stats = sync_blobs(target, source_store=source, on_progress=_progress)
    typer.echo(f"done: {stats}")


@app.command("load-benchmark")
def load_benchmark_cmd(
    directory: Path = typer.Argument(
        ..., help="A verity-build-benchmark output dir (one split, or a parent of several)"
    ),
    to: str | None = typer.Option(
        None, "--to", help="Target DB URL (default: the configured catalog DB)"
    ),
) -> None:
    """Load frozen benchmark split(s) — pairs, folds, provenance, and Verity's
    reference submission — into the catalog DB. Idempotent by split name."""
    from sqlmodel import create_engine

    from .benchmark.io import read_split_dir
    from .benchmark.loader import load_split

    split_dirs = (
        [directory]
        if (directory / "provenance.json").exists()
        else sorted(d for d in directory.iterdir() if (d / "provenance.json").exists())
    )
    if not split_dirs:
        raise typer.BadParameter(f"no provenance.json found under {directory}")

    target = create_engine(to) if to else engine
    with Session(target) as session:
        for split_dir in split_dirs:
            artifacts = read_split_dir(split_dir)
            typer.echo(
                f"loading {artifacts.name}: {len(artifacts.pairs)} pairs, "
                f"{len(artifacts.folds)} folds, split_hash "
                f"{artifacts.provenance['split_hash'][:16]}…"
            )
            split = load_split(session, artifacts)
            typer.echo(f"  loaded as split id {split.id}")


@app.command("crawl-study")
def crawl_study_cmd(
    study_guid: str = typer.Argument(..., help="NBTRD study GUID"),
    name: str = typer.Option(..., help="Manifest name/slug"),
    title: str | None = typer.Option(None, help="Study title"),
    caliber: str | None = typer.Option(None, help="Caliber (firearm default)"),
    out: Path | None = typer.Option(None, help="Output path (default: bundled manifests dir)"),
) -> None:
    """Crawl an NBTRD bullet study into a manifest YAML; then `ingest` it."""
    import yaml

    from .harvest.nbtrd import crawl_to_manifest
    from .ingest import MANIFEST_DIR

    typer.echo(f"crawling study {study_guid} ...")
    manifest = crawl_to_manifest(study_guid, name=name, title=title, caliber=caliber)
    out = out or (MANIFEST_DIR / f"{name}.yaml")
    out.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True))
    typer.echo(f"wrote {len(manifest['files'])} scans -> {out}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
