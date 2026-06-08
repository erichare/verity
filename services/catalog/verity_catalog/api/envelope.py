"""The consistent API response envelope: ``{success, data, error, meta}``.

Every JSON response — success *or* error, including framework-raised validation
errors — is wrapped in this shape so clients have a single contract to code
against (see ``docs/data-catalog-plan.md``).
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Meta(BaseModel):
    """Pagination metadata, attached to list responses."""

    total: int
    page: int
    limit: int
    pages: int


class Envelope(BaseModel, Generic[T]):
    """Uniform response wrapper. ``data`` is null on error; ``error`` is null on
    success; ``meta`` carries pagination for list endpoints."""

    success: bool
    data: T | None = None
    error: str | None = None
    meta: Meta | None = None


def ok(data: T, meta: Meta | None = None) -> Envelope[T]:
    return Envelope[T](success=True, data=data, error=None, meta=meta)


def make_meta(total: int, page: int, limit: int) -> Meta:
    pages = (total + limit - 1) // limit if limit else 0
    return Meta(total=total, page=page, limit=limit, pages=pages)
