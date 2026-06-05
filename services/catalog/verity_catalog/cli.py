"""The ``verity-catalog`` command-line interface."""

from __future__ import annotations

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
    with Session(engine) as session:
        stats = ingest_manifest(session, store, manifest_obj, limit=limit)
    typer.echo(f"ingested '{manifest_obj.name}': {stats}")


@app.command("manifests")
def list_manifests() -> None:
    """List the bundled dataset manifests."""
    from .ingest import MANIFEST_DIR

    for path in sorted(MANIFEST_DIR.glob("*.yaml")):
        typer.echo(path.stem)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
