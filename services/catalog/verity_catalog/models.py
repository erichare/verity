"""The normalized catalog schema.

Mirrors NBTRD's real containment hierarchy so that same-source (KM) vs
different-source (KNM) labels and source-disjoint splits fall out for the
validation harness::

    Study ─< Firearm ─< Bullet ─< Land(LEA) ─< Scan
                       └< CartridgeCase ─< Mark ─< Scan
          └< Tool ─< Toolmark ─< Scan

``Instrument`` is a shared reference entity. Every ``Scan`` carries a
``content_hash`` into the blob store plus source provenance, so the catalog +
store together form a reproducible, pinned dataset.
"""

# NB: do NOT add ``from __future__ import annotations`` here — SQLModel needs the
# relationship annotations (e.g. ``list["Firearm"]``) as real forward refs, not
# strings, or SQLAlchemy 2.0 mapper configuration fails.

from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

# Allowed string values (kept as plain strings for SQLite/Postgres portability).
MODALITIES = ("x3p_3d", "png_2d", "profile_1d")
MARK_TYPES = ("breech_face", "firing_pin", "ejector", "aperture_shear")
TWIST = ("left", "right")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Study(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_study_source_extid"),)

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # "figshare" | "nbtrd"
    external_id: str = Field(index=True)  # DOI / NBTRD GUID
    title: str
    creator: str | None = None
    references: str | None = None
    persistence: bool = Field(default=False, index=True)
    consecutively_manufactured: bool = Field(default=False, index=True)
    nist_measurement: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_utcnow)

    firearms: list["Firearm"] = Relationship(back_populates="study")
    tools: list["Tool"] = Relationship(back_populates="study")


class Firearm(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="study.id", index=True)
    external_id: str | None = Field(default=None, index=True)
    brand: str | None = Field(default=None, index=True)
    model: str | None = None
    caliber: str | None = Field(default=None, index=True)
    n_lands: int | None = Field(default=None, index=True)
    twist: str | None = None  # one of TWIST
    breech_face_class: str | None = Field(default=None, index=True)
    firing_pin_class: str | None = Field(default=None, index=True)

    study: Study | None = Relationship(back_populates="firearms")
    bullets: list["Bullet"] = Relationship(back_populates="firearm")
    cartridge_cases: list["CartridgeCase"] = Relationship(back_populates="firearm")


class Bullet(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    firearm_id: int = Field(foreign_key="firearm.id", index=True)
    external_id: str | None = Field(default=None, index=True)
    label: str | None = None
    brand: str | None = None
    weight: float | None = None
    surface_material: str | None = None

    firearm: Firearm | None = Relationship(back_populates="bullets")
    lands: list["Land"] = Relationship(back_populates="bullet")


class Land(SQLModel, table=True):
    """A land-engraved area (LEA) on a bullet."""

    id: int | None = Field(default=None, primary_key=True)
    bullet_id: int = Field(foreign_key="bullet.id", index=True)
    external_id: str | None = Field(default=None, index=True)
    position: int | None = None  # land number around the bullet

    bullet: Bullet | None = Relationship(back_populates="lands")
    scans: list["Scan"] = Relationship(back_populates="land")


class CartridgeCase(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    firearm_id: int = Field(foreign_key="firearm.id", index=True)
    external_id: str | None = Field(default=None, index=True)
    label: str | None = None
    brand: str | None = None

    firearm: Firearm | None = Relationship(back_populates="cartridge_cases")
    marks: list["Mark"] = Relationship(back_populates="cartridge_case")


class Mark(SQLModel, table=True):
    """A breech-face / firing-pin / ejector / aperture-shear region on a case."""

    id: int | None = Field(default=None, primary_key=True)
    cartridge_case_id: int = Field(foreign_key="cartridgecase.id", index=True)
    external_id: str | None = Field(default=None, index=True)
    mark_type: str = Field(index=True)  # one of MARK_TYPES

    cartridge_case: CartridgeCase | None = Relationship(back_populates="marks")
    scans: list["Scan"] = Relationship(back_populates="mark")


class Tool(SQLModel, table=True):
    """A mark-making tool (e.g. a screwdriver) — the source of a striated
    toolmark, the analog of a ``Firearm`` for bullets. Hangs off a ``Study``."""

    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="study.id", index=True)
    external_id: str | None = Field(default=None, index=True)  # e.g. "T01"
    kind: str | None = Field(default=None, index=True)  # e.g. "slotted screwdriver"
    brand: str | None = None

    study: Study | None = Relationship(back_populates="tools")
    toolmarks: list["Toolmark"] = Relationship(back_populates="tool")


class Toolmark(SQLModel, table=True):
    """A single striated mark made by one tool edge — the analog of a bullet
    ``Land`` or a cartridge ``Mark``. Same-source (KM) is the mark-generating
    edge; the parent ``Tool`` is the coarser physical source."""

    id: int | None = Field(default=None, primary_key=True)
    tool_id: int = Field(foreign_key="tool.id", index=True)
    external_id: str | None = Field(default=None, index=True)  # full mark id, e.g. "T01LA-F80-01"
    edge: str | None = Field(default=None, index=True)  # mark-generating edge, e.g. "T01LA"
    side: str | None = None  # tool face / side, e.g. "A" / "B"
    angle_deg: float | None = None  # angle of attack, if recorded

    tool: Tool | None = Relationship(back_populates="toolmarks")
    scans: list["Scan"] = Relationship(back_populates="toolmark")


class Instrument(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    external_id: str | None = Field(default=None, index=True)
    manufacturer: str | None = None
    model: str | None = None
    kind: str | None = None  # e.g. "disc-scanning confocal microscope"

    scans: list["Scan"] = Relationship(back_populates="instrument")


class Scan(SQLModel, table=True):
    """A single measurement: an X3P 3D scan, a 2D image, or a 1D profile.
    Attached to exactly one parent — a ``Land`` (bullet), a ``Mark`` (cartridge
    case), or a ``Toolmark`` (tool)."""

    id: int | None = Field(default=None, primary_key=True)
    land_id: int | None = Field(default=None, foreign_key="land.id", index=True)
    mark_id: int | None = Field(default=None, foreign_key="mark.id", index=True)
    toolmark_id: int | None = Field(default=None, foreign_key="toolmark.id", index=True)
    instrument_id: int | None = Field(default=None, foreign_key="instrument.id", index=True)

    modality: str = Field(default="x3p_3d", index=True)  # one of MODALITIES
    magnification: str | None = None
    lateral_resolution_x: float | None = Field(default=None, index=True)
    lateral_resolution_y: float | None = None
    light_source: str | None = None

    content_hash: str = Field(index=True)  # SHA-256 into the blob store
    size_bytes: int
    filename: str | None = None

    source: str = Field(index=True)  # "figshare" | "nbtrd"
    source_ref: str  # DOI / GUID / URL the scan came from
    x3p_meta_json: str | None = None  # X3P-embedded metadata, as JSON
    fetched_at: datetime = Field(default_factory=_utcnow)

    land: Land | None = Relationship(back_populates="scans")
    mark: Mark | None = Relationship(back_populates="scans")
    toolmark: Toolmark | None = Relationship(back_populates="scans")
    instrument: Instrument | None = Relationship(back_populates="scans")
    traces: list["ScanTrace"] = Relationship(back_populates="scan")


class ScanTrace(SQLModel, table=True):
    """Per-scan algorithmic trace.

    Records the pipeline-stage artifacts for one land scan — raw / bandpassed /
    rotated / cropped surfaces and the 1-D signature, stored as content-addressed
    blobs in the *artifact* store — plus the orientation/crop metadata. One row
    per ``(scan, pipeline_version)``. A trace is regenerable from the scan, so it
    is a cache (with a version), never source data."""

    __table_args__ = (
        UniqueConstraint("scan_id", "pipeline_version", name="uq_scantrace_scan_pipeline"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scan.id", index=True)
    pipeline_version: str = Field(index=True)
    content_hash_scan: str = Field(index=True)  # = Scan.content_hash (denormalized)

    # Pipeline parameters (reproducibility).
    lambda_s: float | None = None
    lambda_c: float | None = None
    degree: int = 2
    keep: float = 0.5
    orient: bool = True

    # Orientation + groove-crop results.
    striae_angle_deg: float | None = None
    tilt_deg: float | None = None
    crop_lo: int | None = None
    crop_hi: int | None = None
    n_signature: int | None = None

    # Content hashes into the artifact store (composite PNG + npz array bundle).
    png_hash: str | None = Field(default=None, index=True)
    npz_hash: str | None = Field(default=None, index=True)

    created_at: datetime = Field(default_factory=_utcnow)

    scan: Scan | None = Relationship(back_populates="traces")


class PairDiagnostic(SQLModel, table=True):
    """A bullet-pair comparison diagnostic: the CCF-matrix structure features and
    a rendered PNG (content-addressed in the artifact store). Stored for the
    hardest KM/KNM pairs — the ones that carry the remaining discrimination
    headroom — so the failure modes can be inspected and tracked over time."""

    id: int | None = Field(default=None, primary_key=True)
    study_id: int = Field(foreign_key="study.id", index=True)
    bullet_a_id: int = Field(foreign_key="bullet.id", index=True)
    bullet_b_id: int = Field(foreign_key="bullet.id", index=True)
    pipeline_version: str = Field(index=True)
    label: int = Field(index=True)  # 1 = KM (same barrel), 0 = KNM

    offset: int | None = None
    diag_mean: float | None = None
    diag_min: float | None = None
    diag_contrast: float | None = None
    offset_margin: float | None = None
    lag_coherence: float | None = None

    png_hash: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)


class BenchmarkSplit(SQLModel, table=True):
    """A frozen open-benchmark split — the public contract.

    Pairs and folds are produced by the engine's ``verity-build-benchmark`` and
    loaded verbatim; ``split_hash`` commits to the pairs, labels, and fold
    structure (hash equality ⇒ same benchmark). ``provenance`` is the full
    builder provenance JSON, served with the replication kit."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # e.g. "bullets-v1"
    title: str
    modality: str = Field(index=True)
    split_hash: str = Field(index=True)
    protocol_version: int = 1
    n_pairs: int
    n_km: int
    n_sources: int
    n_folds: int
    provenance: str  # builder provenance.json, verbatim
    created_at: datetime = Field(default_factory=_utcnow)

    folds: list["BenchmarkFold"] = Relationship(back_populates="split")
    pairs: list["BenchmarkPair"] = Relationship(back_populates="split")
    submissions: list["BenchmarkSubmission"] = Relationship(back_populates="split")


class BenchmarkFold(SQLModel, table=True):
    """One frozen source-disjoint evaluation fold: the held-out source set."""

    __table_args__ = (
        UniqueConstraint("split_id", "fold_index", name="uq_benchmarkfold_split_index"),
    )

    id: int | None = Field(default=None, primary_key=True)
    split_id: int = Field(foreign_key="benchmarksplit.id", index=True)
    fold_index: int
    n_test_pairs: int
    test_sources: str  # JSON array of source ids

    split: BenchmarkSplit | None = Relationship(back_populates="folds")


class BenchmarkPair(SQLModel, table=True):
    """One frozen comparison pair. ``pair_id`` is content-derived (SHA-256 over
    the two mark hashes), so it is portable across catalogs; ``folds`` is the
    semicolon-joined list of fold indices in which this pair is a test pair."""

    __table_args__ = (
        UniqueConstraint("split_id", "pair_id", name="uq_benchmarkpair_split_pair"),
    )

    id: int | None = Field(default=None, primary_key=True)
    split_id: int = Field(foreign_key="benchmarksplit.id", index=True)
    pair_id: str = Field(index=True)
    hash_a: str
    hash_b: str
    label: int  # 1 = same source (KM), 0 = different (KNM)
    source_a: str
    source_b: str
    folds: str = ""  # ";"-joined fold indices ("" = never a test pair)

    split: BenchmarkSplit | None = Relationship(back_populates="pairs")


class BenchmarkSubmission(SQLModel, table=True):
    """A scored leaderboard entry. The headline metrics are flattened into
    columns (sortable straight from PostgREST); ``metrics`` keeps the full
    per-fold breakdown. ``is_reference`` marks Verity's own baseline rows."""

    id: int | None = Field(default=None, primary_key=True)
    split_id: int = Field(foreign_key="benchmarksplit.id", index=True)
    submitter: str = Field(index=True)
    method: str
    url: str | None = None
    is_reference: bool = Field(default=False, index=True)

    cllr: float = Field(index=True)
    cllr_std: float
    cllr_min: float
    auc: float
    calibration_loss: float = Field(index=True)  # the headline column
    metrics: str  # full scoring JSON (per-fold rows, pooled, ece)

    created_at: datetime = Field(default_factory=_utcnow)

    split: BenchmarkSplit | None = Relationship(back_populates="submissions")


# Convenience grouping for callers that want to iterate every table.
ALL_MODELS = (
    Study,
    Firearm,
    Bullet,
    Land,
    CartridgeCase,
    Mark,
    Tool,
    Toolmark,
    Instrument,
    Scan,
    ScanTrace,
    PairDiagnostic,
    BenchmarkSplit,
    BenchmarkFold,
    BenchmarkPair,
    BenchmarkSubmission,
)
