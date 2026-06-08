"""FastAPI dependencies: DB session, blob store, and pagination params."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Query
from sqlmodel import Session

from ..db import get_session as _db_get_session
from ..store import BlobStore
from ..store import get_store as _get_store

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


def get_session() -> Iterator[Session]:
    """Yield a catalog DB session (reuses ``verity_catalog.db``)."""
    yield from _db_get_session()


def get_store() -> BlobStore:
    """The configured blob store (local FS by default; S3/R2 when deployed)."""
    return _get_store()


@dataclass(frozen=True)
class Pagination:
    """1-indexed page + capped page size, with the SQL offset derived."""

    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def pagination(
    page: int = Query(1, ge=1, description="1-indexed page number"),
    limit: int = Query(
        DEFAULT_LIMIT, ge=1, le=MAX_LIMIT, description=f"page size (max {MAX_LIMIT})"
    ),
) -> Pagination:
    """Pagination params, with ``limit`` capped at :data:`MAX_LIMIT`."""
    return Pagination(page=page, limit=limit)
