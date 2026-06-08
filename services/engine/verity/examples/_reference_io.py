"""Shared writer for calibration references: ``.npz`` (scores, labels, cluster IDs) +
a provenance ``.json`` sidecar.

Every bundled reference carries the source/barrel/slide IDs needed for the *clustered*
bootstrap (the honest finite-reference uncertainty) and a provenance record — the exact
scorer config, the datasets and their content, the generation commit, and the computed
diagnostics — so a court-grade LR can be traced to the data and code that produced it.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from verity.decision import DEFAULT_SCORER_CONFIG, ScorerConfig, cllr, cllr_min, roc_auc
from verity.decision.lr import ScoreLRModel

FORMAT_VERSION = 1


def git_short_hash() -> str | None:
    """The repo's short commit hash, or ``None`` if unavailable (no git / not a repo)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001 - provenance is best-effort, never fatal
        return None


def reference_diagnostics(scores: np.ndarray, labels: np.ndarray) -> dict:
    """The reference's own discrimination + calibration cost, computed the way the API
    reports them (bounded LR via ``ScoreLRModel``)."""
    model = ScoreLRModel(lr_bound="auto").fit(scores, labels)
    ref_lr = model.predict_lr(scores)
    return {
        "n_km": int((labels == 1).sum()),
        "n_knm": int((labels == 0).sum()),
        "auc": float(roc_auc(scores, labels)),
        "cllr": float(cllr(ref_lr[labels == 1], ref_lr[labels == 0])),
        "cllr_min": float(cllr_min(scores, labels)),
    }


@dataclass(frozen=True)
class ReferenceArtifact:
    path: Path
    provenance: dict


def write_reference(
    out_path: Path,
    *,
    scores: np.ndarray,
    labels: np.ndarray,
    cluster_ids: list[str] | np.ndarray,
    name: str,
    generator: str,
    seed: int | None,
    datasets: list[dict],
    cluster_scheme: str = "pair-source-set",
    config: ScorerConfig | None = None,
    write: bool = True,
) -> ReferenceArtifact:
    """Write ``<name>.npz`` + ``<name>.provenance.json``. Set ``write=False`` to compute
    the provenance (diagnostics included) without touching disk — useful for validating
    a regenerated reference against the shipped one before promoting it."""
    cfg = config or DEFAULT_SCORER_CONFIG
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    # Fixed-width unicode so cluster_ids.tobytes() is stable (the bootstrap cache key).
    clusters = np.asarray(cluster_ids).astype("U")
    diagnostics = reference_diagnostics(scores, labels)
    provenance = {
        "format_version": FORMAT_VERSION,
        "name": name,
        "generator": generator,
        "git_commit": git_short_hash(),
        "seed": seed,
        "scorer": cfg.to_dict(),
        "scorer_config_hash": cfg.config_hash,
        "cluster_scheme": cluster_scheme,
        "n_sources": int(np.unique(clusters).size),
        "datasets": datasets,
        "diagnostics": diagnostics,
    }
    if write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(
            out_path,
            scores=scores,
            labels=labels,
            cluster_ids=clusters,
            format_version=np.asarray(FORMAT_VERSION),
        )
        out_path.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return ReferenceArtifact(path=out_path, provenance=provenance)
