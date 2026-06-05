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
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from . import models
from .harvest.base import RemoteFile, Source, UrlListSource
from .harvest.figshare import FigshareSource
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
    persistence: bool = False
    consecutively_manufactured: bool = False
    nist_measurement: bool = False


class SourceSpec(BaseModel):
    kind: str  # "url_list" | "figshare"
    article_id: int | None = None


class FileEntry(BaseModel):
    name: str
    url: str


class Manifest(BaseModel):
    name: str
    title: str | None = None
    study: StudySpec
    firearm_defaults: FirearmDefaults = Field(default_factory=FirearmDefaults)
    source: SourceSpec
    files: list[FileEntry] = Field(default_factory=list)


def load_manifest(name_or_path: str | Path) -> Manifest:
    """Load a manifest by file path, or by name from the bundled manifests dir."""
    path = Path(name_or_path)
    if not path.exists():
        path = MANIFEST_DIR / f"{name_or_path}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {name_or_path}")
    return Manifest.model_validate(yaml.safe_load(path.read_text()))


def build_source(manifest: Manifest) -> Source:
    if manifest.source.kind == "url_list":
        return UrlListSource([RemoteFile(name=f.name, url=f.url) for f in manifest.files])
    if manifest.source.kind == "figshare":
        if manifest.source.article_id is None:
            raise ValueError("figshare source requires 'article_id'")
        return FigshareSource(manifest.source.article_id)
    raise ValueError(f"unknown source kind: {manifest.source.kind!r}")


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

    Idempotent and **resumable**: a scan already present (matched by its source
    URL) is skipped *without* re-downloading, so an interrupted pull can simply
    be re-run."""
    study = get_or_create_study(session, manifest.study)
    source = source or build_source(manifest)

    files = list(source.discover())
    if limit is not None:
        files = files[:limit]

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
