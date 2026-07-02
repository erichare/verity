"""Pydantic read-models (API DTOs) and the scan facet filter.

These are explicit read schemas — distinct from the SQLModel table classes — so
the wire contract is stable and decoupled from storage internals. ``from_attributes``
lets them be built straight from ORM rows.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import SOURCES

# The self-documenting facet description — derived from models.SOURCES so the
# OpenAPI docs can't drift from the sources actually ingested.
SOURCE_FACET_DOC = f"Provenance source: {' | '.join(repr(s) for s in SOURCES)}"


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
    toolmark_id: int | None = None
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
    blob_available: bool = Field(
        default=False,
        description=(
            "Whether this scan's content-addressed blob is currently present in "
            "the public store. When false, the catalog serves the metadata only "
            "and `GET /scans/{id}/x3p` returns 404 until the blob is synced."
        ),
    )


class ScanFilter(BaseModel):
    """Facets for ``GET /scans``. All optional; combined with AND. The resolution
    facets filter on ``lateral_resolution_x`` (µm)."""

    caliber: str | None = Field(None, description="Firearm caliber, e.g. '9mm Luger'")
    n_lands: int | None = Field(None, description="Number of lands on the firearm")
    source: str | None = Field(None, description=SOURCE_FACET_DOC)
    modality: str | None = Field(None, description="'x3p_3d' | 'png_2d' | 'profile_1d'")
    study_id: int | None = Field(
        None,
        description=(
            "Restrict to one study — covers bullet-land, cartridge-mark, and "
            "toolmark scans alike"
        ),
    )
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
    n_files: int = Field(
        description=(
            "Files in the dataset: the manifest's static file list when it has "
            "one, else the scans ingested into the catalog for its study."
        )
    )
    n_resolved: int = Field(
        description="How many of those files are pinned in the catalog (scan id + content hash)."
    )


class PinnedScan(BaseModel):
    """One entry in a resolved dataset: the manifest file plus, when the scan has
    been ingested, its catalog id + content hash (the pinned, reproducible address)."""

    name: str
    url: str
    scan_id: int | None = None
    content_hash: str | None = None
    size_bytes: int | None = None


class DatasetDetail(DatasetSummary):
    """A resolved dataset: the pinned scan list with content hashes. ``resolution``
    says how the list was pinned (see the field description)."""

    resolution: str = Field(
        description=(
            "'manifest' — the recipe's static file URLs matched to Scan.source_ref; "
            "'catalog' — the recipe discovers its files at ingest time, so the "
            "entries are the study's ingested scans; 'pending' — a "
            "discover-at-ingest recipe with nothing ingested yet (empty list, "
            "honestly flagged rather than silently rendered empty)."
        )
    )
    note: str | None = Field(
        None, description="Human-readable explanation for non-'manifest' resolutions."
    )
    files: list[PinnedScan]


class BenchmarkSplitSummary(_Read):
    name: str
    title: str
    modality: str
    split_hash: str
    protocol_version: int
    n_pairs: int
    n_km: int
    n_sources: int
    n_folds: int
    created_at: datetime


class BenchmarkSplitDetail(BenchmarkSplitSummary):
    """Summary plus the builder provenance (protocol, contract, datasets,
    scorer config hash) and the current submission count."""

    provenance: dict
    n_submissions: int


class LeaderboardEntry(_Read):
    submitter: str
    method: str
    url: str | None = None
    is_reference: bool
    cllr: float
    cllr_std: float
    cllr_min: float
    auc: float
    calibration_loss: float
    created_at: datetime


class BenchmarkSubmissionRequest(BaseModel):
    """One submission: identity + one LR per frozen pair, as either a
    ``{pair_id: lr}`` object or a ``pair_id,lr`` CSV string (exactly one)."""

    submitter: str = Field(min_length=1, max_length=80)
    method: str = Field(min_length=1, max_length=120)
    url: str | None = Field(default=None, max_length=300)
    lrs: dict[str, float] | None = None
    csv: str | None = None

    @field_validator("url")
    @classmethod
    def _url_is_http(cls, value: str | None) -> str | None:
        """The leaderboard renders ``url`` as a link, so only absolute http(s)
        URLs are stored — never ``javascript:``/``data:``/scheme-less strings."""
        if value is None or not value.strip():
            return None  # absent/empty stays allowed (rendered as no link)
        try:
            parts = urlsplit(value)
        except ValueError as exc:
            raise ValueError(f"url is not a valid URL: {exc}") from exc
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(
                "url must be an absolute http:// or https:// URL "
                "(e.g. https://example.org/my-method)"
            )
        return value


class BenchmarkSubmissionResult(BaseModel):
    split: str
    split_hash: str
    submitter: str
    method: str
    metrics: dict


class HealthStatus(BaseModel):
    status: str
    database: str
    store_backend: str
    # Exact blob count is an O(n) listing (a full bucket walk on S3), so it is only
    # populated when the caller opts in with ``?count=true``; the default health probe
    # leaves it null and just confirms the store is reachable.
    store_count: int | None = None
    scan_count: int


class VersionInfo(BaseModel):
    name: str
    version: str
