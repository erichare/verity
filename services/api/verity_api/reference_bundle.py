"""Load a calibration reference *bundle*: scores + labels + (when present) per-pair
cluster IDs and a provenance sidecar.

Backward-compatible by construction — a legacy scores-only ``.npz`` loads with
``cluster_ids=None`` and ``provenance={}``, so the API keeps serving it (just without
the clustered bootstrap or drift check). New references carry both, unlocking the honest
clustered credible interval and the scorer-config drift guard.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ReferenceBundle:
    scores: np.ndarray
    labels: np.ndarray
    cluster_ids: np.ndarray | None
    name: str
    provenance: dict

    @property
    def scorer_config_hash(self) -> str | None:
        return self.provenance.get("scorer_config_hash")


def load_bundle(npz_path: Path, *, name: str) -> ReferenceBundle:
    """Load ``<name>.npz`` (+ optional ``<name>.provenance.json``) into a bundle."""
    data = np.load(npz_path, allow_pickle=False)
    cluster_ids = data["cluster_ids"] if "cluster_ids" in data.files else None
    sidecar = npz_path.with_suffix(".provenance.json")
    provenance: dict = {}
    if sidecar.exists():
        provenance = json.loads(sidecar.read_text())
    return ReferenceBundle(
        scores=data["scores"],
        labels=data["labels"],
        cluster_ids=cluster_ids,
        name=name,
        provenance=provenance,
    )
