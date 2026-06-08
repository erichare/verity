"""``/healthz`` and ``/version`` — liveness + build info."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from ... import __version__, models
from ...config import get_settings
from ..deps import get_session, get_store
from ..envelope import Envelope, ok
from ..schemas import HealthStatus, VersionInfo

router = APIRouter(tags=["meta"])


@router.get("/healthz", summary="Liveness + DB/store status", response_model=Envelope[HealthStatus])
def healthz(
    session: Session = Depends(get_session), store=Depends(get_store)
) -> Envelope[HealthStatus]:
    """Report DB connectivity (scan count) and blob-store reachability (blob
    count). A failure in either surfaces as a non-200 via the exception handler."""
    settings = get_settings()
    scan_count = session.exec(select(func.count()).select_from(models.Scan)).one()
    store_count = store.count()
    return ok(
        HealthStatus(
            status="ok",
            database=settings.database_url.split("://", 1)[0],  # scheme only (no creds)
            store_backend=settings.blob_store_backend,
            store_count=store_count,
            scan_count=scan_count,
        )
    )


@router.get("/version", summary="Service name + version", response_model=Envelope[VersionInfo])
def version() -> Envelope[VersionInfo]:
    return ok(VersionInfo(name="verity-catalog", version=__version__))
