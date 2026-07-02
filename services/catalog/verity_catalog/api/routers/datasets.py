"""``/datasets`` — named, pinned dataset recipes (manifests) resolved against the
catalog.

A dataset is a ``manifests/<name>.yaml`` recipe. Resolution has two modes:

- **manifest** — the recipe carries a static ``files:`` URL list (``url_list``
  sources); each URL is matched to ``Scan.source_ref`` and annotated with the
  ingested scan's catalog id + content hash.
- **catalog** — the recipe discovers its file list at ingest time (``github`` /
  ``figshare`` sources carry no static list), so the pinned entries are the
  scans actually ingested for the manifest's study. When nothing has been
  ingested yet the dataset is flagged ``resolution: "pending"`` instead of
  silently rendering an empty list.

Either way the result is a pinned list (URL → content hash) — the
reproducibility entry point the validation harness consumes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from ... import models
from ...ingest import MANIFEST_DIR, Manifest, StudySpec, load_manifest, load_manifest_by_name
from ..deps import get_session
from ..envelope import Envelope, ok
from ..queries import scan_in_study
from ..schemas import DatasetDetail, DatasetSummary, PinnedScan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _summary(manifest: Manifest, *, n_files: int, n_resolved: int) -> DatasetSummary:
    return DatasetSummary(
        name=manifest.name,
        title=manifest.title,
        source=manifest.study.source,
        external_id=manifest.study.external_id,
        n_files=n_files,
        n_resolved=n_resolved,
    )


def _find_study(session: Session, spec: StudySpec) -> models.Study | None:
    return session.exec(
        select(models.Study).where(
            models.Study.source == spec.source,
            models.Study.external_id == spec.external_id,
        )
    ).first()


def _study_scans(session: Session, spec: StudySpec) -> list[models.Scan]:
    """Every ingested scan of the manifest's study, across all three containment
    paths (bullet lands, cartridge marks, toolmarks)."""
    study = _find_study(session, spec)
    if study is None or study.id is None:
        return []
    return list(
        session.exec(
            select(models.Scan).where(scan_in_study(study.id)).order_by(models.Scan.id)
        ).all()
    )


def _count_study_scans(session: Session, spec: StudySpec) -> int:
    study = _find_study(session, spec)
    if study is None or study.id is None:
        return 0
    return session.exec(
        select(func.count(models.Scan.id)).where(scan_in_study(study.id))
    ).one()


@router.get(
    "",
    summary="List named datasets (manifests)",
    response_model=Envelope[list[DatasetSummary]],
)
def list_datasets(session: Session = Depends(get_session)) -> Envelope[list[DatasetSummary]]:
    """Every bundled dataset recipe, with ``n_files`` (the recipe's file list, or
    the ingested scans for discover-at-ingest recipes) and ``n_resolved`` (how
    many of those are pinned in the catalog) — so a large-but-unpinned manifest
    can't read as pinned data."""
    # One query resolves every manifest: the catalog's full source_ref set is
    # small (one row per ingested scan), so membership tests happen in memory
    # instead of one giant IN clause per manifest.
    ingested_refs = set(session.exec(select(models.Scan.source_ref)).all())
    summaries: list[DatasetSummary] = []
    for path in sorted(MANIFEST_DIR.glob("*.yaml")):
        try:
            manifest = load_manifest(path)
        except Exception:  # noqa: BLE001 - skip an unparseable manifest, don't 500 the list
            logger.exception("skipping unparseable dataset manifest %s", path)
            continue
        if manifest.files:
            n_files = len(manifest.files)
            n_resolved = sum(1 for f in manifest.files if f.url in ingested_refs)
        else:
            # Discover-at-ingest recipe: the pinned list is whatever was
            # ingested for its study, so both counts are the catalog count.
            n_files = n_resolved = _count_study_scans(session, manifest.study)
        summaries.append(_summary(manifest, n_files=n_files, n_resolved=n_resolved))
    return ok(summaries)


@router.get(
    "/{name}",
    summary="Resolve a dataset → pinned scan list with content hashes",
    response_model=Envelope[DatasetDetail],
)
def get_dataset(
    name: str, session: Session = Depends(get_session)
) -> Envelope[DatasetDetail]:
    """Resolve a manifest and pin it against the catalog. Recipes with a static
    file list match each file to a ``Scan`` by ``source_ref``
    (``resolution: "manifest"``); recipes that discover their files at ingest
    time pin the scans ingested for their study (``resolution: "catalog"``), or
    are flagged ``resolution: "pending"`` when nothing has been ingested yet."""
    try:
        # ``name`` is untrusted: resolve it strictly within the bundled manifests
        # directory so it cannot traverse to arbitrary files.
        manifest = load_manifest_by_name(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"dataset {name!r} not found") from exc

    if manifest.files:
        # One query for every scan referenced by this manifest, keyed by source URL.
        urls = [f.url for f in manifest.files]
        rows = session.exec(
            select(models.Scan).where(models.Scan.source_ref.in_(urls))
        ).all()
        by_ref = {r.source_ref: r for r in rows}

        files: list[PinnedScan] = []
        resolved = 0
        for entry in manifest.files:
            scan = by_ref.get(entry.url)
            if scan is not None:
                resolved += 1
            files.append(
                PinnedScan(
                    name=entry.name,
                    url=entry.url,
                    scan_id=scan.id if scan else None,
                    content_hash=scan.content_hash if scan else None,
                    size_bytes=scan.size_bytes if scan else None,
                )
            )
        detail = DatasetDetail(
            **_summary(manifest, n_files=len(manifest.files), n_resolved=resolved).model_dump(),
            resolution="manifest",
            note=None,
            files=files,
        )
        return ok(detail)

    # No static file list: github/figshare recipes discover their files at
    # ingest time, so resolve from the catalog instead — the ingested scans of
    # the manifest's study, pinned by content hash.
    scans = _study_scans(session, manifest.study)
    files = [
        PinnedScan(
            name=scan.filename or scan.content_hash,
            url=scan.source_ref,
            scan_id=scan.id,
            content_hash=scan.content_hash,
            size_bytes=scan.size_bytes,
        )
        for scan in scans
    ]
    study_key = f"{manifest.study.source}/{manifest.study.external_id}"
    if files:
        resolution = "catalog"
        note = (
            f"This recipe discovers its file list at ingest time "
            f"({manifest.source.kind} source), so the entries are the "
            f"{len(files)} scans ingested for study {study_key}, pinned by "
            "content hash."
        )
    else:
        resolution = "pending"
        note = (
            f"This recipe discovers its file list at ingest time "
            f"({manifest.source.kind} source) and no scans for study "
            f"{study_key} are in the catalog yet, so there is nothing to pin."
        )
    detail = DatasetDetail(
        **_summary(manifest, n_files=len(files), n_resolved=len(files)).model_dump(),
        resolution=resolution,
        note=note,
        files=files,
    )
    return ok(detail)
