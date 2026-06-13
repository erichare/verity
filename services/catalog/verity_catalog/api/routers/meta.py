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
    session: Session = Depends(get_session),
    store=Depends(get_store),
    count: bool = False,
) -> Envelope[HealthStatus]:
    """Report DB connectivity (scan count) and blob-store reachability. Reachability is a
    *cheap* probe (a single-key list on S3), not a full bucket walk, so this stays fast
    under the platform's frequent health checks. A failure in either surfaces as a non-200
    via the exception handler. Pass ``?count=true`` to also include the exact blob count
    (an O(n) listing — for diagnostics, e.g. confirming a blob sync, not the hot path)."""
    settings = get_settings()
    scan_count = session.exec(select(func.count()).select_from(models.Scan)).one()
    store.probe()  # cheap reachability; raises -> non-200 if the store is unreachable
    return ok(
        HealthStatus(
            status="ok",
            database=settings.database_url.split("://", 1)[0],  # scheme only (no creds)
            store_count=store.count() if count else None,
            store_backend=settings.blob_store_backend,
            scan_count=scan_count,
        )
    )


@router.get("/version", summary="Service name + version", response_model=Envelope[VersionInfo])
def version() -> Envelope[VersionInfo]:
    return ok(VersionInfo(name="verity-catalog", version=__version__))
