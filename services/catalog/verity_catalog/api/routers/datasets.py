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

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from ... import models
from ...ingest import MANIFEST_DIR, Manifest, StudySpec, load_manifest, load_manifest_by_name
from ..deps import get_session, get_store
from ..envelope import Envelope, ok
from ..queries import scan_in_study
from ..schemas import (
    DatasetDetail,
    DatasetSnapshot,
    DatasetSnapshotScan,
    DatasetSummary,
    PinnedScan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["datasets"])

SOURCE_LICENSES = {
    "nbtrd": "public-domain-us-gov",
    "csafe-isu": "cc-by-4.0",
    "figshare": "cc-by-4.0",
    "tmarks": "mit",
}


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


def _snapshot_hierarchy(
    session: Session, scan: models.Scan
) -> dict[str, int | str | None]:
    """Resolve a scan's physical-source hierarchy into stable scalar IDs."""
    values: dict[str, int | str | None] = {
        "study_id": None,
        "firearm_id": None,
        "firearm_external_id": None,
        "bullet_id": None,
        "bullet_external_id": None,
        "land_id": None,
        "land_external_id": None,
        "land_position": None,
        "cartridge_case_id": None,
        "mark_id": None,
        "tool_id": None,
        "toolmark_id": None,
    }
    if scan.land_id is not None:
        land = session.get(models.Land, scan.land_id)
        if land is None:
            return values
        bullet = session.get(models.Bullet, land.bullet_id)
        firearm = session.get(models.Firearm, bullet.firearm_id) if bullet else None
        values.update(
            study_id=firearm.study_id if firearm else None,
            firearm_id=firearm.id if firearm else None,
            firearm_external_id=firearm.external_id if firearm else None,
            bullet_id=bullet.id if bullet else None,
            bullet_external_id=bullet.external_id if bullet else None,
            land_id=land.id,
            land_external_id=land.external_id,
            land_position=land.position,
        )
    elif scan.mark_id is not None:
        mark = session.get(models.Mark, scan.mark_id)
        case = session.get(models.CartridgeCase, mark.cartridge_case_id) if mark else None
        firearm = session.get(models.Firearm, case.firearm_id) if case else None
        values.update(
            study_id=firearm.study_id if firearm else None,
            firearm_id=firearm.id if firearm else None,
            firearm_external_id=firearm.external_id if firearm else None,
            cartridge_case_id=case.id if case else None,
            mark_id=mark.id if mark else None,
        )
    elif scan.toolmark_id is not None:
        toolmark = session.get(models.Toolmark, scan.toolmark_id)
        tool = session.get(models.Tool, toolmark.tool_id) if toolmark else None
        values.update(
            study_id=tool.study_id if tool else None,
            tool_id=tool.id if tool else None,
            toolmark_id=toolmark.id if toolmark else None,
        )
    return values


def _snapshot_manifest_hash(
    *,
    dataset: DatasetDetail,
    license_name: str,
    scans: list[DatasetSnapshotScan],
) -> str:
    """Hash immutable identity/provenance, deliberately excluding store state."""
    identity_scans = [
        scan.model_dump(exclude={"blob_available", "download_url"}) for scan in scans
    ]
    payload = {
        "schema_version": 1,
        "dataset": dataset.name,
        "title": dataset.title,
        "source": dataset.source,
        "external_id": dataset.external_id,
        "license": license_name,
        "resolution": dataset.resolution,
        "n_files": dataset.n_files,
        "n_resolved": dataset.n_resolved,
        "scans": identity_scans,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@router.get(
    "/{name}/snapshot",
    summary="Export one versioned, content-hashed dataset snapshot",
    response_model=Envelope[DatasetSnapshot],
)
def get_dataset_snapshot(
    name: str,
    session: Session = Depends(get_session),
    store=Depends(get_store),
) -> Envelope[DatasetSnapshot]:
    """Return the complete offline-ingest contract in one response.

    The snapshot includes provenance, licensing, physical-source hierarchy,
    download addresses, and current blob availability. ``manifest_hash`` covers
    immutable identity/provenance fields and therefore remains stable when a
    previously pending blob finishes syncing.
    """
    envelope = get_dataset(name, session)
    dataset = envelope.data
    if dataset is None:  # defensive: successful get_dataset always has data
        raise HTTPException(status_code=404, detail=f"dataset {name!r} not found")

    resolved_ids = [entry.scan_id for entry in dataset.files if entry.scan_id is not None]
    rows = (
        session.exec(select(models.Scan).where(models.Scan.id.in_(resolved_ids))).all()
        if resolved_ids
        else []
    )
    by_id = {row.id: row for row in rows}
    present = store.existing({row.content_hash for row in rows})
    license_name = SOURCE_LICENSES.get(dataset.source, "unknown")

    scans: list[DatasetSnapshotScan] = []
    for pinned in dataset.files:
        scan = by_id.get(pinned.scan_id)
        if scan is None:
            scans.append(
                DatasetSnapshotScan(
                    filename=pinned.name,
                    scan_id=None,
                    content_hash=pinned.content_hash,
                    size_bytes=pinned.size_bytes,
                    source=dataset.source,
                    source_ref=pinned.url,
                    license=license_name,
                )
            )
            continue
        scans.append(
            DatasetSnapshotScan(
                filename=scan.filename or pinned.name,
                scan_id=scan.id,
                content_hash=scan.content_hash,
                size_bytes=scan.size_bytes,
                source=scan.source,
                source_ref=scan.source_ref,
                license=SOURCE_LICENSES.get(scan.source, "unknown"),
                modality=scan.modality,
                blob_available=scan.content_hash in present,
                download_url=f"/scans/{scan.id}/x3p",
                **_snapshot_hierarchy(session, scan),
            )
        )

    scans.sort(
        key=lambda row: (
            row.source_ref,
            row.scan_id if row.scan_id is not None else 2**63 - 1,
            row.filename,
        )
    )
    manifest_hash = _snapshot_manifest_hash(
        dataset=dataset,
        license_name=license_name,
        scans=scans,
    )
    complete = (
        dataset.n_files == dataset.n_resolved
        and len(scans) == dataset.n_files
        and all(scan.blob_available for scan in scans)
    )
    return ok(
        DatasetSnapshot(
            dataset=dataset.name,
            title=dataset.title,
            source=dataset.source,
            external_id=dataset.external_id,
            license=license_name,
            resolution=dataset.resolution,
            n_files=dataset.n_files,
            n_resolved=dataset.n_resolved,
            complete=complete,
            manifest_hash=manifest_hash,
            scans=scans,
        )
    )
