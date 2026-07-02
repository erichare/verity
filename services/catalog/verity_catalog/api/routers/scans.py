"""``/scans`` — faceted search over scans, metadata, and the binary X3P blob.

The blob route serves the content-addressed bytes with the SHA-256 as a strong
``ETag`` (conditional ``If-None-Match`` → ``304``). On the S3/R2 deploy backend it
302-redirects to the object URL instead of streaming through the API.

The catalog can be ahead of the public blob store (blobs sync in batches), so
every scan row carries ``blob_available`` — whether its bytes are downloadable
*right now* — and ``/scans`` takes a ``blob_available`` filter. The flag is
computed against the store in one batched lookup per page, never a per-row query.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from ... import models
from ..deps import Pagination, get_session, get_store, pagination
from ..envelope import Envelope, make_meta, ok
from ..queries import scan_in_study
from ..schemas import SOURCE_FACET_DOC, ScanFilter, ScanRead

router = APIRouter(prefix="/scans", tags=["scans"])


def _apply_facets(stmt, flt: ScanFilter):
    """Apply the scan facets to a select statement. caliber/n_lands are firearm
    attributes reached via Land→Bullet→Firearm, so those facets join that path
    (and thereby restrict to bullet-land scans). study_id instead ORs across all
    three containment paths (:func:`scan_in_study`), so mark- and toolmark-based
    scans stay in study-filtered results."""
    if flt.source is not None:
        stmt = stmt.where(models.Scan.source == flt.source)
    if flt.modality is not None:
        stmt = stmt.where(models.Scan.modality == flt.modality)
    if flt.min_resolution is not None:
        stmt = stmt.where(models.Scan.lateral_resolution_x >= flt.min_resolution)
    if flt.max_resolution is not None:
        stmt = stmt.where(models.Scan.lateral_resolution_x <= flt.max_resolution)
    if flt.study_id is not None:
        stmt = stmt.where(scan_in_study(flt.study_id))

    needs_firearm = flt.caliber is not None or flt.n_lands is not None
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
    return stmt


def _read_with_availability(scan: models.Scan, present: set[str]) -> ScanRead:
    """Build the read model with ``blob_available`` from a precomputed batch
    lookup (``model_copy`` because the flag lives in the store, not the row)."""
    return ScanRead.model_validate(scan).model_copy(
        update={"blob_available": scan.content_hash in present}
    )


@router.get(
    "",
    summary="Search scans (faceted + paginated)",
    response_model=Envelope[list[ScanRead]],
)
def list_scans(
    session: Session = Depends(get_session),
    store=Depends(get_store),
    page: Pagination = Depends(pagination),
    caliber: str | None = Query(None, description="Firearm caliber, e.g. '9mm Luger'"),
    n_lands: int | None = Query(None, description="Number of lands on the firearm"),
    source: str | None = Query(None, description=SOURCE_FACET_DOC),
    modality: str | None = Query(None, description="'x3p_3d' | 'png_2d' | 'profile_1d'"),
    min_resolution: float | None = Query(None, description="Min lateral_resolution_x (µm)"),
    max_resolution: float | None = Query(None, description="Max lateral_resolution_x (µm)"),
    study_id: int | None = Query(
        None,
        description=(
            "Restrict to one study — covers bullet-land, cartridge-mark, and "
            "toolmark scans alike"
        ),
    ),
    blob_available: bool | None = Query(
        None,
        description=(
            "Filter by blob presence in the public store: true → only scans "
            "whose bytes are downloadable now; false → only scans whose blobs "
            "are not yet synced (metadata-only)."
        ),
    ),
) -> Envelope[list[ScanRead]]:
    """Faceted scan search. ``meta.total`` is the unpaginated match count, so
    clients can page through the whole result set. Every row carries
    ``blob_available``; when it is false the scan's metadata is served but
    ``/scans/{id}/x3p`` returns 404 until the blob is synced to the public
    store."""
    flt = ScanFilter(
        caliber=caliber,
        n_lands=n_lands,
        source=source,
        modality=modality,
        study_id=study_id,
        min_resolution=min_resolution,
        max_resolution=max_resolution,
    )
    if blob_available is None:
        count_stmt = _apply_facets(select(func.count(models.Scan.id)), flt)
        total = session.exec(count_stmt).one()
        stmt = _apply_facets(select(models.Scan), flt)
        rows = session.exec(
            stmt.order_by(models.Scan.id).offset(page.offset).limit(page.limit)
        ).all()
        present = store.existing({r.content_hash for r in rows})
    else:
        # Blob presence lives in the store, not the DB, so the facet resolves the
        # full match set to (id, hash) — two columns, one query — splits it by
        # store membership (one batched lookup), then pages in memory.
        refs = session.exec(
            _apply_facets(select(models.Scan.id, models.Scan.content_hash), flt).order_by(
                models.Scan.id
            )
        ).all()
        present = store.existing({h for _, h in refs})
        matched = [i for i, h in refs if (h in present) == blob_available]
        total = len(matched)
        page_ids = matched[page.offset : page.offset + page.limit]
        rows = (
            session.exec(
                select(models.Scan)
                .where(models.Scan.id.in_(page_ids))
                .order_by(models.Scan.id)
            ).all()
            if page_ids
            else []
        )
    data = [_read_with_availability(r, present) for r in rows]
    return ok(data, make_meta(total, page.page, page.limit))


@router.get("/{scan_id}", summary="Get one scan's metadata", response_model=Envelope[ScanRead])
def get_scan(
    scan_id: int, session: Session = Depends(get_session), store=Depends(get_store)
) -> Envelope[ScanRead]:
    """One scan's metadata, including ``blob_available`` — whether its bytes are
    currently in the public store (false ⇒ ``/scans/{id}/x3p`` returns 404)."""
    scan = session.get(models.Scan, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail=f"scan {scan_id} not found")
    return ok(_read_with_availability(scan, store.existing({scan.content_hash})))


@router.get(
    "/{scan_id}/x3p",
    summary="Download a scan's X3P bytes (ETag = content hash)",
    response_class=Response,
    responses={
        200: {"content": {"application/x-x3p": {}}, "description": "The X3P bytes"},
        302: {"description": "Redirect to the object URL (S3/R2 backend)"},
        304: {"description": "Not modified (If-None-Match matched the content hash)"},
        404: {
            "description": (
                "Scan not found — or the scan's blob is not yet in the public "
                "store (its metadata is served and `blob_available` is false "
                "until the blob syncs)"
            )
        },
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
    302-redirects to the object URL instead of streaming. Blobs sync to the
    public store in batches, so a scan can be cataloged before its bytes are
    servable — check ``blob_available`` on the scan's metadata first."""
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
        detail = (
            f"scan {scan_id} is cataloged (metadata is served), but its blob "
            f"{scan.content_hash} is not yet in the public store — the blob sync "
            "is pending; check blob_available on /scans/{id} before downloading"
        )
        if scan.modality == "profile_1d":
            detail += (
                ". Note: this scan's original measurement is a 1-D profile, "
                "not an X3P surface"
            )
        raise HTTPException(status_code=404, detail=detail) from exc

    filename = scan.filename or f"{scan.content_hash}.x3p"
    headers = {
        "ETag": etag,
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "public, max-age=31536000, immutable",
    }
    return StreamingResponse(
        iter((data,)), media_type="application/x-x3p", headers=headers
    )
