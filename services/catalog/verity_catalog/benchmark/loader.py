"""Loading a frozen split (and Verity's baseline submission) into the catalog.

Idempotent by split *name*: re-loading replaces the split's folds, pairs, and
reference (``is_reference=True``) submissions — user submissions are preserved
unless the ``split_hash`` changed, in which case they were scored against a
different contract and are dropped with a warning.
"""

from __future__ import annotations

from sqlmodel import Session, delete, select

from .. import models
from .io import SplitArtifacts

_BATCH = 5000


def load_split(session: Session, artifacts: SplitArtifacts) -> models.BenchmarkSplit:
    import json

    prov = artifacts.provenance
    counts = prov["counts"]
    existing = session.exec(
        select(models.BenchmarkSplit).where(models.BenchmarkSplit.name == artifacts.name)
    ).first()

    hash_changed = existing is not None and existing.split_hash != prov["split_hash"]
    if existing is not None:
        session.exec(
            delete(models.BenchmarkPair).where(models.BenchmarkPair.split_id == existing.id)
        )
        session.exec(
            delete(models.BenchmarkFold).where(models.BenchmarkFold.split_id == existing.id)
        )
        sub_filter = models.BenchmarkSubmission.split_id == existing.id
        if not hash_changed:
            sub_filter = sub_filter & (models.BenchmarkSubmission.is_reference == True)  # noqa: E712
        session.exec(delete(models.BenchmarkSubmission).where(sub_filter))
        split = existing
    else:
        split = models.BenchmarkSplit(
            name=artifacts.name,
            title=prov["title"],
            modality=prov["modality"],
            split_hash=prov["split_hash"],
            protocol_version=prov.get("protocol_version", 1),
            n_pairs=counts["n_pairs"],
            n_km=counts["n_km"],
            n_sources=counts["n_sources"],
            n_folds=counts["n_folds"],
            provenance=json.dumps(prov),
        )

    split.title = prov["title"]
    split.modality = prov["modality"]
    split.split_hash = prov["split_hash"]
    split.protocol_version = prov.get("protocol_version", 1)
    split.n_pairs = counts["n_pairs"]
    split.n_km = counts["n_km"]
    split.n_sources = counts["n_sources"]
    split.n_folds = counts["n_folds"]
    split.provenance = json.dumps(prov)
    split.marks_csv_gz = artifacts.marks_csv_gz
    session.add(split)
    session.commit()
    session.refresh(split)

    for fold in artifacts.folds:
        session.add(
            models.BenchmarkFold(
                split_id=split.id,
                fold_index=fold["index"],
                n_test_pairs=fold["n_test_pairs"],
                test_sources=json.dumps(fold["test_sources"]),
            )
        )
    session.commit()

    for start in range(0, len(artifacts.pairs), _BATCH):
        for row in artifacts.pairs[start : start + _BATCH]:
            session.add(
                models.BenchmarkPair(
                    split_id=split.id,
                    pair_id=row["pair_id"],
                    hash_a=row["hash_a"],
                    hash_b=row["hash_b"],
                    label=row["label"],
                    source_a=row["source_a"],
                    source_b=row["source_b"],
                    folds=row["folds"],
                )
            )
        session.commit()

    if artifacts.verity_metrics is not None:
        m = artifacts.verity_metrics
        session.add(
            models.BenchmarkSubmission(
                split_id=split.id,
                submitter="Verity",
                method=prov.get("scorer", {}).get("score_kind", "verity"),
                # The method page lives on the docs host since the app/science
                # split; the old verity.codes/method URL bounces through a 308.
                url="https://docs.verity.codes/method",
                is_reference=True,
                cllr=m["cllr"],
                cllr_std=m["cllr_std"],
                cllr_min=m["cllr_min"],
                auc=m["auc"],
                calibration_loss=m["calibration_loss"],
                metrics=json.dumps(m),
            )
        )
        session.commit()

    return split
