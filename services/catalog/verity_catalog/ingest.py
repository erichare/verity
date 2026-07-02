"""Manifest-driven ingestion.

For each scan in a manifest: fetch it, validate it with ``verity-x3p`` (which
verifies the embedded MD5 and yields metadata), store the bytes in the
content-addressed store, and populate the catalog hierarchy idempotently.
"""

import json
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session, select

from . import models
from .harvest.base import RemoteFile, Source, UrlListSource
from .harvest.figshare import FigshareSource
from .harvest.github import GithubSource
from .store import BlobStore

MANIFEST_DIR = Path(__file__).parent / "manifests"


# --------------------------------------------------------------------------- #
# Manifest schema                                                             #
# --------------------------------------------------------------------------- #
class FirearmDefaults(BaseModel):
    brand: str | None = None
    model: str | None = None
    caliber: str | None = None
    n_lands: int | None = None
    twist: str | None = None


class StudySpec(BaseModel):
    source: str
    external_id: str
    title: str | None = None
    creator: str | None = None
    references: str | None = None
    persistence: bool = False
    consecutively_manufactured: bool = False
    nist_measurement: bool = False


class SourceSpec(BaseModel):
    kind: str  # "url_list" | "figshare" | "github"
    article_id: int | None = None  # figshare
    repo: str | None = None  # github: "owner/name"
    ref: str | None = None  # github: branch/tag (default "main")
    path: str | None = None  # github: directory within the repo
    # github: walk subdirectories (one git/trees?recursive=1 call); discovered
    # file names then keep their path-relative subdirectory ("TW01/TW01-01.x3p").
    recursive: bool = False


class FileEntry(BaseModel):
    name: str
    url: str


class Manifest(BaseModel):
    name: str
    title: str | None = None
    # The catalog entity these scans hang off: bullet lands (LEAs) or cartridge-case
    # marks. Selects the containment path the ingest builds and the filename parser
    # it applies. Defaults to "bullet" so existing manifests are unchanged.
    entity: str = "bullet"  # "bullet" | "cartridge"
    mark_type: str = "breech_face"  # cartridge only: one of models.MARK_TYPES
    study: StudySpec
    firearm_defaults: FirearmDefaults = Field(default_factory=FirearmDefaults)
    source: SourceSpec
    files: list[FileEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_entity(self) -> "Manifest":
        if self.entity not in ("bullet", "cartridge"):
            raise ValueError(f"entity must be 'bullet' or 'cartridge', got {self.entity!r}")
        if self.entity == "cartridge" and self.mark_type not in models.MARK_TYPES:
            raise ValueError(
                f"mark_type must be one of {models.MARK_TYPES}, got {self.mark_type!r}"
            )
        return self


def resolve_manifest_name(name: str) -> Path:
    """Resolve a bundled-manifest *name* to its path inside :data:`MANIFEST_DIR`.

    The returned path is taken from a listing of ``MANIFEST_DIR`` — the untrusted
    *name* is only ever compared against the stems of files that already exist,
    never used to construct a filesystem path. An attacker-controlled name
    therefore cannot traverse outside the bundled manifests directory; a name
    that matches no bundled manifest simply yields ``FileNotFoundError``.
    """
    for candidate in MANIFEST_DIR.glob("*.yaml"):
        if candidate.stem == name:
            return candidate
    raise FileNotFoundError(f"manifest not found: {name!r}")


def _read_manifest(path: Path) -> Manifest:
    return Manifest.model_validate(yaml.safe_load(path.read_text()))


def load_manifest_by_name(name: str) -> Manifest:
    """Load a bundled manifest **by name only**, confined to :data:`MANIFEST_DIR`.

    Use this for untrusted input (e.g. an API path parameter): it can never
    resolve to a file outside the bundled manifests directory.
    """
    return _read_manifest(resolve_manifest_name(name))


def load_manifest(name_or_path: str | Path) -> Manifest:
    """Load a manifest from an explicit file path, or by bundled name.

    An existing file path is read as-is — this branch is for **trusted, local**
    callers only (the CLI and directory globs). Bare names are resolved via
    :func:`resolve_manifest_name`, which confines them to ``MANIFEST_DIR``. For
    untrusted input, call :func:`load_manifest_by_name` instead.
    """
    path = Path(name_or_path)
    if path.is_file():
        return _read_manifest(path)
    return load_manifest_by_name(str(name_or_path))


def build_source(manifest: Manifest) -> Source:
    kind = manifest.source.kind
    if kind == "url_list":
        return UrlListSource([RemoteFile(name=f.name, url=f.url) for f in manifest.files])
    if kind == "figshare":
        if manifest.source.article_id is None:
            raise ValueError("figshare source requires 'article_id'")
        return FigshareSource(manifest.source.article_id)
    if kind == "github":
        if not manifest.source.repo:
            raise ValueError("github source requires 'repo' (owner/name)")
        return GithubSource(
            manifest.source.repo,
            ref=manifest.source.ref or "main",
            path=manifest.source.path or "",
            recursive=manifest.source.recursive,
        )
    raise ValueError(f"unknown source kind: {kind!r}")


# --------------------------------------------------------------------------- #
# Filename parsing                                                            #
# --------------------------------------------------------------------------- #
_LEA_RE = re.compile(
    r"[Bb]arrel\s*[_-]?\s*(\d+).*?[Bb]ullet\s*[_-]?\s*(\d+).*?[Ll]and\s*[_-]?\s*(\d+)"
)


def parse_lea(name: str) -> tuple[int, int, int] | None:
    """Extract ``(barrel, bullet, land)`` from a scan filename, or ``None``."""
    m = _LEA_RE.search(name)
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


# Known-source cartridge scans follow a ``… {slide}-{case}.x3p`` convention
# (e.g. ``Fadul 1-1.x3p``). Questioned cases are lettered (``Fadul A.x3p``) and
# have no known source slide, so they fail this match and are skipped — mirroring
# how the NBTRD harvester skips questioned firearm buckets.
_SLIDE_CASE_RE = re.compile(r"(\d+)\s*-\s*(\d+)\.x3p$", re.IGNORECASE)


def parse_slide_case(name: str) -> tuple[int, int] | None:
    """Extract ``(slide, case)`` from a known-source cartridge scan filename, or
    ``None`` for questioned/unlabelled cases."""
    m = _SLIDE_CASE_RE.search(name)
    return (int(m[1]), int(m[2])) if m else None


def cartridge_source_identity(name: str) -> tuple[str, str] | None:
    """Resolve a harvested cartridge scan name to ``(firearm_external_id,
    case_external_id)``, or ``None`` when no source is attributable.

    Directory-labeled names (from a recursive harvest, e.g. ``TW01/TW01-01.x3p``)
    take the directory as the source identity — the registered rule for the
    Weller set (pre-registration §4.2): the scan's SOURCE is its slide directory,
    and it must sit in **exactly one** (one directory component); anything else —
    nested deeper, or an empty component — is unattributable and skipped. The
    directory takes precedence over the ``{slide}-{case}`` filename regex, which
    would otherwise mislabel ``TW01-01.x3p``-style names.

    Flat names (no directory component) keep the existing filename convention
    (``Fadul 1-1.x3p`` → ``Slide1``/``Slide1-Case1``); questioned/unlabelled
    flat files still return ``None``, so Fadul ingest is unchanged.
    """
    if "/" in name:
        parts = name.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None  # not exactly one slide directory -> unattributable
        directory, filename = parts
        return directory, Path(filename).stem
    slide_case = parse_slide_case(name)
    if slide_case is None:
        return None
    slide, case = slide_case
    return f"Slide{slide}", f"Slide{slide}-Case{case}"


# --------------------------------------------------------------------------- #
# Idempotent catalog upserts                                                  #
# --------------------------------------------------------------------------- #
def get_or_create_study(session: Session, spec: StudySpec) -> models.Study:
    study = session.exec(
        select(models.Study).where(
            models.Study.source == spec.source,
            models.Study.external_id == spec.external_id,
        )
    ).first()
    if study:
        return study
    study = models.Study(
        source=spec.source,
        external_id=spec.external_id,
        title=spec.title or spec.external_id,
        creator=spec.creator,
        references=spec.references,
        persistence=spec.persistence,
        consecutively_manufactured=spec.consecutively_manufactured,
        nist_measurement=spec.nist_measurement,
    )
    session.add(study)
    session.commit()
    session.refresh(study)
    return study


def get_or_create_firearm(
    session: Session, study: models.Study, external_id: str, defaults: FirearmDefaults
) -> models.Firearm:
    firearm = session.exec(
        select(models.Firearm).where(
            models.Firearm.study_id == study.id,
            models.Firearm.external_id == external_id,
        )
    ).first()
    if firearm:
        return firearm
    firearm = models.Firearm(study_id=study.id, external_id=external_id, **defaults.model_dump())
    session.add(firearm)
    session.commit()
    session.refresh(firearm)
    return firearm


def get_or_create_bullet(
    session: Session, firearm: models.Firearm, external_id: str
) -> models.Bullet:
    bullet = session.exec(
        select(models.Bullet).where(
            models.Bullet.firearm_id == firearm.id,
            models.Bullet.external_id == external_id,
        )
    ).first()
    if bullet:
        return bullet
    bullet = models.Bullet(firearm_id=firearm.id, external_id=external_id)
    session.add(bullet)
    session.commit()
    session.refresh(bullet)
    return bullet


def get_or_create_land(
    session: Session, bullet: models.Bullet, position: int, external_id: str
) -> models.Land:
    land = session.exec(
        select(models.Land).where(
            models.Land.bullet_id == bullet.id,
            models.Land.position == position,
        )
    ).first()
    if land:
        return land
    land = models.Land(bullet_id=bullet.id, position=position, external_id=external_id)
    session.add(land)
    session.commit()
    session.refresh(land)
    return land


def get_or_create_cartridge_case(
    session: Session, firearm: models.Firearm, external_id: str, *, label: str | None = None
) -> models.CartridgeCase:
    case = session.exec(
        select(models.CartridgeCase).where(
            models.CartridgeCase.firearm_id == firearm.id,
            models.CartridgeCase.external_id == external_id,
        )
    ).first()
    if case:
        return case
    case = models.CartridgeCase(firearm_id=firearm.id, external_id=external_id, label=label)
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


def get_or_create_mark(
    session: Session, cartridge_case: models.CartridgeCase, external_id: str, mark_type: str
) -> models.Mark:
    mark = session.exec(
        select(models.Mark).where(
            models.Mark.cartridge_case_id == cartridge_case.id,
            models.Mark.external_id == external_id,
        )
    ).first()
    if mark:
        return mark
    mark = models.Mark(
        cartridge_case_id=cartridge_case.id, external_id=external_id, mark_type=mark_type
    )
    session.add(mark)
    session.commit()
    session.refresh(mark)
    return mark


# --------------------------------------------------------------------------- #
# X3P validation + ingest                                                     #
# --------------------------------------------------------------------------- #
def validate_and_extract(data: bytes) -> dict:
    """Read the X3P with ``verity-x3p`` (verifying its MD5) and return metadata."""
    try:
        import verity_x3p
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "ingestion requires the 'verity-x3p' binding — install the 'ingest' extra"
        ) from exc

    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        surface = verity_x3p.read_x3p(path)  # raises on bad checksum / malformed file
        return {
            "nx": surface.nx,
            "ny": surface.ny,
            "increment_x_m": surface.increment_x,
            "increment_y_m": surface.increment_y,
            "z_type": surface.z_type,
            "creator": surface.creator,
            "comment": surface.comment,
        }
    finally:
        Path(path).unlink(missing_ok=True)


def ingest_scan(
    session: Session,
    store: BlobStore,
    data: bytes,
    *,
    name: str,
    source: str,
    source_ref: str,
    land: models.Land | None = None,
    mark: models.Mark | None = None,
    instrument: models.Instrument | None = None,
) -> models.Scan:
    """Validate, store, and catalog one scan (deduplicated by content hash)."""
    meta = validate_and_extract(data)
    content_hash = store.put(data)

    existing = session.exec(
        select(models.Scan).where(models.Scan.content_hash == content_hash)
    ).first()
    if existing:
        return existing

    scan = models.Scan(
        land_id=land.id if land else None,
        mark_id=mark.id if mark else None,
        instrument_id=instrument.id if instrument else None,
        modality="x3p_3d",
        content_hash=content_hash,
        size_bytes=len(data),
        filename=name,
        lateral_resolution_x=(meta["increment_x_m"] or 0.0) * 1e6,  # metres -> µm
        lateral_resolution_y=(meta["increment_y_m"] or 0.0) * 1e6,
        source=source,
        source_ref=source_ref,
        x3p_meta_json=json.dumps(meta),
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)
    return scan


def ingest_manifest(
    session: Session,
    store: BlobStore,
    manifest: Manifest,
    *,
    limit: int | None = None,
    source: Source | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict:
    """Ingest a manifest's scans into the catalog. ``source`` may be injected
    (e.g. in tests) to avoid network access.

    Dispatches on ``manifest.entity`` to build the bullet (Firearm → Bullet → Land)
    or cartridge (Firearm → CartridgeCase → Mark) containment path.

    Idempotent and **resumable**: a scan already present (matched by its source
    URL) is skipped *without* re-downloading, so an interrupted pull can simply
    be re-run."""
    study = get_or_create_study(session, manifest.study)
    source = source or build_source(manifest)

    files = list(source.discover())
    if limit is not None:
        files = files[:limit]

    if manifest.entity == "cartridge":
        return _ingest_cartridge(session, store, manifest, study, source, files, on_progress)
    return _ingest_bullet(session, store, manifest, study, source, files, on_progress)


def _ingest_bullet(
    session: Session,
    store: BlobStore,
    manifest: Manifest,
    study: models.Study,
    source: Source,
    files: list[RemoteFile],
    on_progress: Callable[[int, int, str], None] | None,
) -> dict:
    """Build Study → Firearm(Barrel) → Bullet → Land(LEA) → Scan from LEA-named
    files. Non-LEA filenames are counted in ``skipped_no_lea``."""
    stats = {"files": len(files), "ingested": 0, "already_present": 0, "skipped_no_lea": 0}
    total = len(files)
    for index, remote in enumerate(files, start=1):
        lea = parse_lea(remote.name)
        if lea is None:
            stats["skipped_no_lea"] += 1
        elif session.exec(select(models.Scan).where(models.Scan.source_ref == remote.url)).first():
            stats["already_present"] += 1  # resume: don't re-download
        else:
            barrel, bullet, land_no = lea
            firearm = get_or_create_firearm(
                session, study, f"Barrel{barrel}", manifest.firearm_defaults
            )
            bullet_row = get_or_create_bullet(session, firearm, f"Barrel{barrel}_Bullet{bullet}")
            land = get_or_create_land(session, bullet_row, land_no, remote.name)
            data = source.fetch(remote)
            ingest_scan(
                session,
                store,
                data,
                name=remote.name,
                source=manifest.study.source,
                source_ref=remote.url,
                land=land,
            )
            stats["ingested"] += 1
        if on_progress:
            on_progress(index, total, remote.name)
    return stats


def _ingest_cartridge(
    session: Session,
    store: BlobStore,
    manifest: Manifest,
    study: models.Study,
    source: Source,
    files: list[RemoteFile],
    on_progress: Callable[[int, int, str], None] | None,
) -> dict:
    """Build Study → Firearm(Slide) → CartridgeCase → Mark(mark_type) → Scan.

    Source identity comes from :func:`cartridge_source_identity`: the slide
    directory for directory-labeled names (recursive harvests, e.g. Weller
    ``TW01/TW01-01.x3p``), the ``{slide}-{case}`` filename convention for flat
    names (Fadul). Unattributable files — questioned/unlabelled flat names, or
    names not in exactly one slide directory — are counted in
    ``skipped_no_match``, so the pre-registration's mechanical exclusion rule
    (§5.5 rule 2) is reported by ingest; content-hash dedup (rule 3) is
    enforced downstream by :func:`ingest_scan`."""
    stats = {"files": len(files), "ingested": 0, "already_present": 0, "skipped_no_match": 0}
    total = len(files)
    for index, remote in enumerate(files, start=1):
        identity = cartridge_source_identity(remote.name)
        if identity is None:
            stats["skipped_no_match"] += 1
        elif session.exec(select(models.Scan).where(models.Scan.source_ref == remote.url)).first():
            stats["already_present"] += 1  # resume: don't re-download
        else:
            firearm_ext, case_ext = identity
            firearm = get_or_create_firearm(session, study, firearm_ext, manifest.firearm_defaults)
            cartridge_case = get_or_create_cartridge_case(
                session, firearm, case_ext, label=Path(remote.name).stem
            )
            mark = get_or_create_mark(
                session,
                cartridge_case,
                f"{case_ext}-{manifest.mark_type}",
                manifest.mark_type,
            )
            data = source.fetch(remote)
            ingest_scan(
                session,
                store,
                data,
                name=remote.name,
                source=manifest.study.source,
                source_ref=remote.url,
                mark=mark,
            )
            stats["ingested"] += 1
        if on_progress:
            on_progress(index, total, remote.name)
    return stats
