"""``/datasets`` — named, pinned dataset recipes (manifests) resolved against the
catalog.

A dataset is a ``manifests/<name>.yaml`` recipe; resolving it matches each
manifest file URL to ``Scan.source_ref`` and attaches the ingested scan's catalog
id + content hash. That pinned list (URL → content hash) is the reproducibility
entry point the validation harness consumes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ... import models
from ...ingest import MANIFEST_DIR, Manifest, load_manifest
from ..deps import get_session
from ..envelope import Envelope, ok
from ..schemas import DatasetDetail, DatasetSummary, PinnedScan

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _summary(manifest: Manifest) -> DatasetSummary:
    return DatasetSummary(
        name=manifest.name,
        title=manifest.title,
        source=manifest.study.source,
        external_id=manifest.study.external_id,
        n_files=len(manifest.files),
    )


@router.get(
    "",
    summary="List named datasets (manifests)",
    response_model=Envelope[list[DatasetSummary]],
)
def list_datasets() -> Envelope[list[DatasetSummary]]:
    summaries: list[DatasetSummary] = []
    for path in sorted(MANIFEST_DIR.glob("*.yaml")):
        try:
            summaries.append(_summary(load_manifest(path)))
        except Exception:  # noqa: BLE001 - skip an unparseable manifest, don't 500 the list
            continue
    return ok(summaries)


@router.get(
    "/{name}",
    summary="Resolve a dataset → pinned scan list with content hashes",
    response_model=Envelope[DatasetDetail],
)
def get_dataset(
    name: str, session: Session = Depends(get_session)
) -> Envelope[DatasetDetail]:
    """Resolve a manifest and pin it against the catalog: each manifest file is
    matched to a ``Scan`` by ``source_ref`` and annotated with the ingested scan's
    id + content hash (null when that file hasn't been ingested yet)."""
    try:
        manifest = load_manifest(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"dataset {name!r} not found") from exc

    # One query for every scan referenced by this manifest, keyed by source URL.
    urls = [f.url for f in manifest.files]
    by_ref: dict[str, models.Scan] = {}
    if urls:
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
        **_summary(manifest).model_dump(), n_resolved=resolved, files=files
    )
    return ok(detail)
