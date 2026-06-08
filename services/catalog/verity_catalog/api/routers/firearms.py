"""``/firearms`` — barrels within a study (the KM/KNM identity boundary)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from ... import models
from ..deps import Pagination, get_session, pagination
from ..envelope import Envelope, make_meta, ok
from ..schemas import FirearmRead

router = APIRouter(prefix="/firearms", tags=["firearms"])


@router.get("", summary="List firearms", response_model=Envelope[list[FirearmRead]])
def list_firearms(
    session: Session = Depends(get_session),
    page: Pagination = Depends(pagination),
    study_id: int | None = Query(None, description="Restrict to one study"),
) -> Envelope[list[FirearmRead]]:
    stmt = select(models.Firearm)
    count_stmt = select(func.count()).select_from(models.Firearm)
    if study_id is not None:
        stmt = stmt.where(models.Firearm.study_id == study_id)
        count_stmt = count_stmt.where(models.Firearm.study_id == study_id)
    total = session.exec(count_stmt).one()
    rows = session.exec(
        stmt.order_by(models.Firearm.id).offset(page.offset).limit(page.limit)
    ).all()
    data = [FirearmRead.model_validate(r) for r in rows]
    return ok(data, make_meta(total, page.page, page.limit))


@router.get("/{firearm_id}", summary="Get one firearm", response_model=Envelope[FirearmRead])
def get_firearm(
    firearm_id: int, session: Session = Depends(get_session)
) -> Envelope[FirearmRead]:
    firearm = session.get(models.Firearm, firearm_id)
    if firearm is None:
        raise HTTPException(status_code=404, detail=f"firearm {firearm_id} not found")
    return ok(FirearmRead.model_validate(firearm))
