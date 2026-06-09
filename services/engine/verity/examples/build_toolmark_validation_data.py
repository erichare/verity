"""Persist the tmaRks toolmark (striated, 1-D) validation numbers the white paper quotes
— the source of truth behind the toolmark row, the third reduction in the CMR table.

The **deployed CMR-1D** numbers are recomputed here from the *committed* reference
``toolmark_tmaRks.npz`` (no network): in-sample AUC / Cllr / Cllr_min and the
source-disjoint summary (mean ± sd over folds, no tool-edge spanning train and test).
Two comparison **baselines** are recorded as context (not recomputed here, and flagged
``reproducible: false``):

* the *same-pipeline* global 1-D cross-correlation (``align_1d``) on the same set — the
  pre-CMR baseline (``verity-toolmark-tmaRks``); and
* the Chumbley ``toolmaRk`` specialist, whose head-to-head Verity runs on the *ameslab*
  set (``verity-toolmark-chumbley-proof``) — a different, smaller set, so it is recorded
  as a pointer, not a tmaRks number.

    cd services/engine && uv run verity-toolmark-validation-data
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from verity.report_validation import compute_validation_summary

from ._reference_io import barrels_from_clusters, git_short_hash, load_reference

_ROOT = Path(__file__).resolve().parents[4]
_REF = _ROOT / "services/api/verity_api/references/toolmark_tmaRks.npz"
_OUT = _ROOT / "docs/whitepaper/data/toolmark_tmaRks.json"

# Recorded context. Neither is recomputed from the committed reference: the global
# baseline needs the tmaRks profiles (cache or R+network); the Chumbley head-to-head is
# demonstrated on a *different* set (ameslab) and needs R + toolmaRk.
_BASELINES = [
    {
        "method": "global 1-D CCF (same pipeline as bullets)",
        "scorer": "align_1d (1-D cross-correlation, no congruence consensus)",
        "auc": 0.94,
        "cllr_range": [0.25, 0.45],
        "level": "tool-edge",
        "measured_by": "verity-toolmark-tmaRks",
        "requires": "tmaRks cache (or R+network on first fetch)",
        "reproducible": False,
        "note": "the pre-CMR baseline on the same set; strong transfer of the bullets pipeline",
    },
    {
        "method": "Chumbley U (specialist)",
        "scorer": "toolmaRk::chumbley_non_random",
        "demonstrated_on": "ameslab (16 profiles / 7 tools) — proof-of-concept, NOT tmaRks",
        "measured_by": "verity-toolmark-chumbley-proof",
        "requires": "git+network+R(toolmaRk)",
        "reproducible": False,
        "note": "the field-standard toolmark statistic; head-to-head shown separately on ameslab",
    },
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(write: bool = True) -> dict:
    """Compute the toolmark validation payload from the committed reference and
    (optionally) write ``docs/whitepaper/data/toolmark_tmaRks.json``."""
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

    payload = {
        "reference": summary.reference_name,
        "domain": "striated-toolmark",
        "deployed_scorer": "CMR-1D (congruent matching regions, 1-D striae; Chumbley/CMS)",
        "reproducible_from": "services/api/verity_api/references/toolmark_tmaRks.npz",
        "source_level": "tool-edge (the mark generator)",
        "summary": summary.to_dict(),
        "baselines": _BASELINES,
        "provenance": {
            "generator": "build_toolmark_validation_data",
            "git_commit": git_short_hash(),
            "source_reference_sha256": _sha256(_REF),
            "generated_at": summary.generated_at,
            "note": (
                "Deployed CMR-1D numbers recomputed from the committed reference (no network). "
                "Baselines are recorded context from the named harnesses (the Chumbley "
                "head-to-head is on ameslab, a different set); not recomputed here."
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
