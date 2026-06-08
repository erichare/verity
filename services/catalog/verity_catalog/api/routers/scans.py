"""``/scans`` — faceted search over scans, metadata, and the binary X3P blob.

The blob route serves the content-addressed bytes with the SHA-256 as a strong
``ETag`` (conditional ``If-None-Match`` → ``304``). On the S3/R2 deploy backend it
302-redirects to the object URL instead of streaming through the API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from ... import models
from ..deps import Pagination, get_session, get_store, pagination
from ..envelope import Envelope, make_meta, ok
from ..schemas import ScanFilter, ScanRead

router = APIRouter(prefix="/scans", tags=["scans"])


def _apply_facets(stmt, flt: ScanFilter):
    """Apply the scan facets to a select statement. caliber/n_lands are firearm
    attributes, reached via Land→Bullet→Firearm, so those facets join that path
    (and thereby restrict to bullet-land scans)."""
    if flt.source is not None:
        stmt = stmt.where(models.Scan.source == flt.source)
    if flt.modality is not None:
        stmt = stmt.where(models.Scan.modality == flt.modality)
    if flt.min_resolution is not None:
        stmt = stmt.where(models.Scan.lateral_resolution_x >= flt.min_resolution)
    if flt.max_resolution is not None:
        stmt = stmt.where(models.Scan.lateral_resolution_x <= flt.max_resolution)

    needs_firearm = (
        flt.caliber is not None or flt.n_lands is not None or flt.study_id is not None
    )
    if needs_firearm:
        stmt = (
            stmt.join(models.Land, models.Scan.land_id == models.Land.id)
            .join(models.Bullet, models.Land.bullet_id == models.Bullet.id)
            .join(models.Firearm, models.Bullet.firearm_id == models.Firearm.id)
        )
        if flt.caliber is not None:
            stmt = stmt.where(models.Firearm.caliber == flt.caliber)
        if flt.n_lands is not None:
            stmt = stmt.where(models.Firearm.n_lands == flt.n_lands)
        if flt.study_id is not None:
            stmt = stmt.where(models.Firearm.study_id == flt.study_id)
    return stmt


@router.get(
    "",
    summary="Search scans (faceted + paginated)",
    response_model=Envelope[list[ScanRead]],
)
def list_scans(
    session: Session = Depends(get_session),
    page: Pagination = Depends(pagination),
    caliber: str | None = Query(None, description="Firearm caliber, e.g. '9mm Luger'"),
    n_lands: int | None = Query(None, description="Number of lands on the firearm"),
    source: str | None = Query(None, description="Provenance source ('nbtrd' | 'figshare')"),
    modality: str | None = Query(None, description="'x3p_3d' | 'png_2d'"),
    min_resolution: float | None = Query(None, description="Min lateral_resolution_x (µm)"),
    max_resolution: float | None = Query(None, description="Max lateral_resolution_x (µm)"),
    study_id: int | None = Query(None, description="Restrict to one study"),
) -> Envelope[list[ScanRead]]:
    """Faceted scan search. ``meta.total`` is the unpaginated match count, so
    clients can page through the whole result set."""
    flt = ScanFilter(
        caliber=caliber,
        n_lands=n_lands,
        source=source,
        modality=modality,
        study_id=study_id,
        min_resolution=min_resolution,
        max_resolution=max_resolution,
    )
    count_stmt = _apply_facets(select(func.count(models.Scan.id)), flt)
    total = session.exec(count_stmt).one()
    stmt = _apply_facets(select(models.Scan), flt)
    rows = session.exec(
        stmt.order_by(models.Scan.id).offset(page.offset).limit(page.limit)
    ).all()
    data = [ScanRead.model_validate(r) for r in rows]
    return ok(data, make_meta(total, page.page, page.limit))


@router.get("/{scan_id}", summary="Get one scan's metadata", response_model=Envelope[ScanRead])
def get_scan(scan_id: int, session: Session = Depends(get_session)) -> Envelope[ScanRead]:
    scan = session.get(models.Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"scan {scan_id} not found")
    return ok(ScanRead.model_validate(scan))


@router.get(
    "/{scan_id}/x3p",
    summary="Download a scan's X3P bytes (ETag = content hash)",
    response_class=Response,
    responses={
        200: {"content": {"application/x-x3p": {}}, "description": "The X3P bytes"},
        302: {"description": "Redirect to the object URL (S3/R2 backend)"},
        304: {"description": "Not modified (If-None-Match matched the content hash)"},
        404: {"description": "Scan or blob not found"},
    },
)
def get_scan_x3p(
    scan_id: int,
    session: Session = Depends(get_session),
    store=Depends(get_store),
    if_none_match: str | None = Header(None, alias="If-None-Match"),
):
    """Serve the content-addressed X3P bytes. The SHA-256 is the strong ``ETag``;
    a matching ``If-None-Match`` returns ``304``. On the S3/R2 backend this
    302-redirects to the object URL instead of streaming."""
    scan = session.get(models.Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"scan {scan_id} not found")

    etag = f'"{scan.content_hash}"'
    # Conditional request: a client that already has this exact content can skip
    # the transfer (content hash never changes for a given scan, so this is safe).
    if if_none_match and scan.content_hash in if_none_match:
        return Response(status_code=304, headers={"ETag": etag})

    # S3/R2 deploy path: redirect to the object URL (offload the byte transfer).
    public_url = getattr(store, "public_url", None)
    if public_url is not None:
        url = public_url(scan.content_hash)
        if url:
            return RedirectResponse(url=url, status_code=302, headers={"ETag": etag})

    try:
        data = store.get(scan.content_hash)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"blob {scan.content_hash} missing from store"
        ) from exc

    filename = scan.filename or f"{scan.content_hash}.x3p"
    headers = {
        "ETag": etag,
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "public, max-age=31536000, immutable",
    }
    return StreamingResponse(
        iter((data,)), media_type="application/x-x3p", headers=headers
    )
