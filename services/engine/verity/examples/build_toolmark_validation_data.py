"""Persist the tmaRks toolmark (striated, 1-D) validation numbers the white paper quotes
— the source of truth behind the toolmark row, the third reduction in the CMR table.

The **deployed CMR-1D** numbers are recomputed here from the *committed* reference
``toolmark_tmaRks.npz`` (no network): in-sample AUC / Cllr / Cllr_min and the
source-disjoint summary (by tool-edge). Two **baselines** are read from ``baselines.json``
(measured + re-lockable via ``verity-relock-baselines``):

* the *same-pipeline* global 1-D cross-correlation (``align_1d``) on the same tmaRks set —
  the directly comparable pre-CMR baseline (CMR-1D should beat it); and
* the Chumbley ``toolmaRk`` specialist, measured on the *ameslab* set (a different,
  smaller set), recorded as cross-method context, not a tmaRks number.

    cd services/engine && uv run verity-toolmark-validation-data
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from verity.report_validation import compute_validation_summary

from ._reference_io import barrels_from_clusters, git_short_hash, load_reference
from .relock_baselines import load_baselines

_ROOT = Path(__file__).resolve().parents[4]
_REF = _ROOT / "services/api/verity_api/references/toolmark_tmaRks.npz"
_OUT = _ROOT / "docs/whitepaper/data/toolmark_tmaRks.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baselines() -> list[dict]:
    """The toolmark comparison baselines, with measured numbers from baselines.json."""
    bl = load_baselines() or {}
    tm_global = bl.get("toolmark_tmaRks_global", {})
    chum = (bl.get("toolmark_chumbley_ameslab", {}) or {}).get("chumbley", {})
    return [
        {
            "method": "global 1-D CCF (same pipeline as bullets)",
            "scorer": "align_1d (1-D cross-correlation, no congruence consensus)",
            "dataset": "tmaRks (tool-edge) — directly comparable to CMR-1D",
            "auc": tm_global.get("pooled_auc"),
            "cllr": tm_global.get("sd_cllr"),
            "cllr_sd": tm_global.get("sd_cllr_sd"),
            "measured_by": "verity-relock-baselines",
            "measured": bool(tm_global),
            "reproducible": False,  # needs R/caches to re-lock; not offline from the committed npz
            "note": "pre-CMR baseline on the same set; CMR-1D beats it (lower Cllr, higher AUC)",
        },
        {
            "method": "Chumbley U (specialist)",
            "scorer": "toolmaRk::chumbley_non_random",
            "dataset": "ameslab (7 tools) — different, smaller set; NOT tmaRks",
            "auc": chum.get("pooled_auc"),
            "cllr": chum.get("sd_cllr"),
            "cllr_sd": chum.get("sd_cllr_sd"),
            "measured_by": "verity-relock-baselines",
            "measured": bool(chum),
            "reproducible": False,  # needs R/caches to re-lock; not offline from the committed npz
            "note": "field-standard toolmark statistic, measured on ameslab; cross-method context",
        },
    ]


def build(write: bool = True) -> dict:
    """Compute the toolmark validation payload from the committed reference (+ measured
    baselines) and (optionally) write ``docs/whitepaper/data/toolmark_tmaRks.json``."""
    if not _REF.exists():
        raise FileNotFoundError(
            f"{_REF} not found — build it first: "
            "uv run python -m verity.examples.build_toolmark_reference --write"
        )
    ref = load_reference(_REF)
    barrels_a, barrels_b = barrels_from_clusters(ref.cluster_ids)
    summary = compute_validation_summary(
        ref.scores,
        ref.labels,
        reference_name=(ref.provenance or {}).get("name", "tmaRks toolmarks"),
        domain="striated-toolmark",
        barrels_a=barrels_a,
        barrels_b=barrels_b,
        generated_at=date.today().isoformat(),
    )
    bd = summary.barrel_disjoint or {}
    baselines = _baselines()

    payload = {
        "reference": summary.reference_name,
        "domain": "striated-toolmark",
        "deployed_scorer": "CMR-1D (congruent matching regions, 1-D striae; Chumbley/CMS)",
        "reproducible_from": "services/api/verity_api/references/toolmark_tmaRks.npz",
        "baselines_from": "docs/whitepaper/data/baselines.json (verity-relock-baselines)",
        "source_level": "tool-edge (the mark generator)",
        "summary": summary.to_dict(),
        "baselines": baselines,
        "provenance": {
            "generator": "build_toolmark_validation_data",
            "git_commit": git_short_hash(),
            "source_reference_sha256": _sha256(_REF),
            "generated_at": summary.generated_at,
            "note": (
                "Deployed CMR-1D numbers recomputed from the committed reference (no network). "
                "Baselines read from baselines.json (measured; the Chumbley head-to-head is on "
                "ameslab, a different set). Re-lock with verity-relock-baselines."
            ),
        },
    }

    bd_txt = (
        f"source-disjoint Cllr={bd['cllr_mean']:.3f}±{bd['cllr_std']:.3f} "
        f"AUC={bd['auc_mean']:.3f}±{bd['auc_std']:.3f} ({bd['n_folds']} folds)"
        if bd
        else "source-disjoint: too few tool-edges"
    )
    print(
        f"toolmark (tmaRks, CMR-1D, tool-edge): n_km={summary.n_km} n_knm={summary.n_knm} "
        f"in-sample AUC={summary.auc:.3f} Cllr={summary.cllr:.3f} Cllr_min={summary.cllr_min:.3f}"
    )
    print(f"  {bd_txt}")
    if not load_baselines():
        print("  WARNING: baselines.json missing — baselines null; run verity-relock-baselines.")
    if write:
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"WROTE {_OUT}")
    else:
        print(f"DRY-RUN (pass write=True to save): {_OUT}")
    return payload


def main() -> None:
    build(write=True)


if __name__ == "__main__":
    main()
