"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401  (import registers all tables on SQLModel.metadata)
from .config import get_settings


def make_engine(url: str | None = None) -> Engine:
    settings = get_settings()
    url = url or settings.database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


engine: Engine = make_engine()


def create_all(target_engine: Engine | None = None) -> None:
    """Create every table. Convenience for local-first init and tests; the
    canonical, versioned path for deployments is ``alembic upgrade head``."""
    SQLModel.metadata.create_all(target_engine or engine)


def get_session() -> Iterator[Session]:
    """FastAPI-style dependency yielding a session."""
    with Session(engine) as session:
        yield session
