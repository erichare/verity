"""Shared SQL fragments for the read API."""

from __future__ import annotations

from sqlalchemy import or_
from sqlmodel import select

from .. import models


def scan_in_study(study_id: int):
    """A SQL condition: the scan belongs to ``study_id``.

    A scan hangs off exactly one of three parents, each with its own path to the
    study — bullet lands (Land → Bullet → Firearm), cartridge-case marks
    (Mark → CartridgeCase → Firearm), and toolmarks (Toolmark → Tool). The study
    facet must OR membership across **all three**, otherwise mark- and
    toolmark-based scans silently vanish from study-filtered results."""
    land_ids = (
        select(models.Land.id)
        .join(models.Bullet, models.Land.bullet_id == models.Bullet.id)
        .join(models.Firearm, models.Bullet.firearm_id == models.Firearm.id)
        .where(models.Firearm.study_id == study_id)
    )
    mark_ids = (
        select(models.Mark.id)
        .join(
            models.CartridgeCase,
            models.Mark.cartridge_case_id == models.CartridgeCase.id,
        )
        .join(models.Firearm, models.CartridgeCase.firearm_id == models.Firearm.id)
        .where(models.Firearm.study_id == study_id)
    )
    toolmark_ids = (
        select(models.Toolmark.id)
        .join(models.Tool, models.Toolmark.tool_id == models.Tool.id)
        .where(models.Tool.study_id == study_id)
    )
    return or_(
        models.Scan.land_id.in_(land_ids),
        models.Scan.mark_id.in_(mark_ids),
        models.Scan.toolmark_id.in_(toolmark_ids),
    )
