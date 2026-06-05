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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
