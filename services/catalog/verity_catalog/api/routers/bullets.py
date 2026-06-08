"""``/bullets/{id}/lands`` and ``/cartridge-cases/{id}/marks`` — the leaf
containers that own scans (bullet lands / cartridge-case marks)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ... import models
from ..deps import get_session
from ..envelope import Envelope, ok
from ..schemas import LandRead, MarkRead

router = APIRouter(tags=["bullets"])


@router.get(
    "/bullets/{bullet_id}/lands",
    summary="List a bullet's lands (LEAs)",
    response_model=Envelope[list[LandRead]],
)
def list_bullet_lands(
    bullet_id: int, session: Session = Depends(get_session)
) -> Envelope[list[LandRead]]:
    if session.get(models.Bullet, bullet_id) is None:
        raise HTTPException(status_code=404, detail=f"bullet {bullet_id} not found")
    rows = session.exec(
        select(models.Land)
        .where(models.Land.bullet_id == bullet_id)
        .order_by(models.Land.position)
    ).all()
    return ok([LandRead.model_validate(r) for r in rows])


@router.get(
    "/cartridge-cases/{cartridge_case_id}/marks",
    summary="List a cartridge case's marks",
    response_model=Envelope[list[MarkRead]],
)
def list_cartridge_case_marks(
    cartridge_case_id: int, session: Session = Depends(get_session)
) -> Envelope[list[MarkRead]]:
    if session.get(models.CartridgeCase, cartridge_case_id) is None:
        raise HTTPException(
            status_code=404, detail=f"cartridge case {cartridge_case_id} not found"
        )
    rows = session.exec(
        select(models.Mark)
        .where(models.Mark.cartridge_case_id == cartridge_case_id)
        .order_by(models.Mark.id)
    ).all()
    return ok([MarkRead.model_validate(r) for r in rows])
