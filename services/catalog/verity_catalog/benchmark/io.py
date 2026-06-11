"""Reading a ``verity-build-benchmark`` output directory.

A split directory contains ``pairs.csv.gz``, ``folds.json``, ``provenance.json``,
optionally ``marks.csv.gz`` (the mark-hash → scan-hash mapping, kept verbatim
for the replication kit), and (for Verity's own baseline row)
``verity_submission.csv.gz`` + ``verity_metrics.json``. This module parses them
into plain Python structures; :mod:`.loader` turns those into catalog rows.
"""

from __future__ import annotations

import csv
import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

PAIR_FIELDS = ("pair_id", "hash_a", "hash_b", "label", "source_a", "source_b", "folds")


@dataclass(frozen=True)
class SplitArtifacts:
    """One parsed split directory."""

    name: str
    provenance: dict
    pairs: list[dict]  # rows with PAIR_FIELDS keys (label as int)
    folds: list[dict]  # {"index", "n_test_pairs", "test_sources"}
    verity_lrs: dict[str, float] = field(default_factory=dict)  # pair_id -> LR
    verity_metrics: dict | None = None
    marks_csv_gz: bytes | None = None  # marks.csv.gz verbatim, if shipped


def read_pairs_csv(path: Path) -> list[dict]:
    with gzip.open(path, "rt", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = set(PAIR_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        rows = []
        for row in reader:
            rows.append({**row, "label": int(row["label"])})
        return rows


def read_submission_csv(path: Path) -> dict[str, float]:
    """``pair_id,lr`` rows → mapping. Values are parsed as floats; validity
    (finite, positive) is the scorer's job so the error message is uniform."""
    with gzip.open(path, "rt", newline="") if path.suffix == ".gz" else path.open(
        newline=""
    ) as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or ()
        if "pair_id" not in fields or "lr" not in fields:
            raise ValueError(f"{path.name}: expected 'pair_id,lr' header")
        return {row["pair_id"]: float(row["lr"]) for row in reader}


def read_split_dir(split_dir: Path) -> SplitArtifacts:
    split_dir = Path(split_dir)
    provenance = json.loads((split_dir / "provenance.json").read_text())
    pairs = read_pairs_csv(split_dir / "pairs.csv.gz")
    folds = json.loads((split_dir / "folds.json").read_text())

    verity_lrs: dict[str, float] = {}
    verity_metrics = None
    sub = split_dir / "verity_submission.csv.gz"
    met = split_dir / "verity_metrics.json"
    if sub.exists() and met.exists():
        verity_lrs = read_submission_csv(sub)
        verity_metrics = json.loads(met.read_text())

    marks = split_dir / "marks.csv.gz"
    marks_csv_gz = marks.read_bytes() if marks.exists() else None

    return SplitArtifacts(
        name=provenance["name"],
        provenance=provenance,
        pairs=pairs,
        folds=folds,
        verity_lrs=verity_lrs,
        verity_metrics=verity_metrics,
        marks_csv_gz=marks_csv_gz,
    )
