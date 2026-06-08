"""``/studies`` — the top of the catalog hierarchy."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from ... import models
from ..deps import Pagination, get_session, pagination
from ..envelope import Envelope, make_meta, ok
from ..schemas import StudyRead

router = APIRouter(prefix="/studies", tags=["studies"])


@router.get("", summary="List studies", response_model=Envelope[list[StudyRead]])
def list_studies(
    session: Session = Depends(get_session),
    page: Pagination = Depends(pagination),
) -> Envelope[list[StudyRead]]:
    total = session.exec(select(func.count()).select_from(models.Study)).one()
    rows = session.exec(
        select(models.Study).order_by(models.Study.id).offset(page.offset).limit(page.limit)
    ).all()
    data = [StudyRead.model_validate(r) for r in rows]
    return ok(data, make_meta(total, page.page, page.limit))


@router.get("/{study_id}", summary="Get one study", response_model=Envelope[StudyRead])
def get_study(
    study_id: int, session: Session = Depends(get_session)
) -> Envelope[StudyRead]:
    study = session.get(models.Study, study_id)
    if study is None:
        raise HTTPException(status_code=404, detail=f"study {study_id} not found")
    return ok(StudyRead.model_validate(study))
