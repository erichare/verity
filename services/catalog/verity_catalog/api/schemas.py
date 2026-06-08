"""Pydantic read-models (API DTOs) and the scan facet filter.

These are explicit read schemas — distinct from the SQLModel table classes — so
the wire contract is stable and decoupled from storage internals. ``from_attributes``
lets them be built straight from ORM rows.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StudyRead(_Read):
    id: int
    source: str
    external_id: str
    title: str
    creator: str | None = None
    references: str | None = None
    persistence: bool
    consecutively_manufactured: bool
    nist_measurement: bool
    created_at: datetime


class FirearmRead(_Read):
    id: int
    study_id: int
    external_id: str | None = None
    brand: str | None = None
    model: str | None = None
    caliber: str | None = None
    n_lands: int | None = None
    twist: str | None = None
    breech_face_class: str | None = None
    firing_pin_class: str | None = None


class BulletRead(_Read):
    id: int
    firearm_id: int
    external_id: str | None = None
    label: str | None = None
    brand: str | None = None
    weight: float | None = None
    surface_material: str | None = None


class LandRead(_Read):
    id: int
    bullet_id: int
    external_id: str | None = None
    position: int | None = None


class MarkRead(_Read):
    id: int
    cartridge_case_id: int
    external_id: str | None = None
    mark_type: str


class ScanRead(_Read):
    id: int
    land_id: int | None = None
    mark_id: int | None = None
    instrument_id: int | None = None
    modality: str
    magnification: str | None = None
    lateral_resolution_x: float | None = None
    lateral_resolution_y: float | None = None
    light_source: str | None = None
    content_hash: str
    size_bytes: int
    filename: str | None = None
    source: str
    source_ref: str
    fetched_at: datetime


class ScanFilter(BaseModel):
    """Facets for ``GET /scans``. All optional; combined with AND. The resolution
    facets filter on ``lateral_resolution_x`` (µm)."""

    caliber: str | None = Field(None, description="Firearm caliber, e.g. '9mm Luger'")
    n_lands: int | None = Field(None, description="Number of lands on the firearm")
    source: str | None = Field(None, description="Provenance source, e.g. 'nbtrd' | 'figshare'")
    modality: str | None = Field(None, description="'x3p_3d' | 'png_2d'")
    study_id: int | None = Field(None, description="Restrict to one study")
    min_resolution: float | None = Field(
        None, description="Minimum lateral_resolution_x in µm (inclusive)"
    )
    max_resolution: float | None = Field(
        None, description="Maximum lateral_resolution_x in µm (inclusive)"
    )


class DatasetSummary(BaseModel):
    """A named, pinned dataset (manifest) — summary form for ``GET /datasets``."""

    name: str
    title: str | None = None
    source: str
    external_id: str
    n_files: int


class PinnedScan(BaseModel):
    """One entry in a resolved dataset: the manifest file plus, when the scan has
    been ingested, its catalog id + content hash (the pinned, reproducible address)."""

    name: str
    url: str
    scan_id: int | None = None
    content_hash: str | None = None
    size_bytes: int | None = None


class DatasetDetail(DatasetSummary):
    """A resolved dataset: the pinned scan list with content hashes pulled from the
    catalog by matching ``Scan.source_ref`` to the manifest file URLs."""

    n_resolved: int
    files: list[PinnedScan]


class HealthStatus(BaseModel):
    status: str
    database: str
    store_backend: str
    store_count: int
    scan_count: int


class VersionInfo(BaseModel):
    name: str
    version: str
