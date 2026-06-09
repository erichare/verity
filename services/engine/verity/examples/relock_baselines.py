"""Re-lock the recorded comparison baselines behind the CMR validation figures/tables.

The deployed CMR numbers are reproducible offline from the committed references; the
*baselines* they are compared against — the naive global scores and the field-standard
specialists — need the source datasets and, for the specialists, R. So they are measured
HERE and written to ``docs/whitepaper/data/baselines.json`` with provenance, and the
validation-data builders fold these measured values into their JSON. Re-run whenever the
scorer or data changes::

    cd services/engine && uv run verity-relock-baselines

Needs the cached datasets (``~/.cache/verity/{cartridgeCaseScans,tmaRks,ameslab}``) and R
with ``cmcR`` + ``toolmaRk`` for the two specialist baselines. Any section whose data or R
is missing is recorded as an ``error`` string, never fabricated.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np

from verity.decision.metrics import roc_auc
from verity.decision.validation import barrel_disjoint_folds, summarize_folds

from ._reference_io import git_short_hash

_ROOT = Path(__file__).resolve().parents[4]
_OUT = _ROOT / "docs/whitepaper/data/baselines.json"


def load_baselines() -> dict | None:
    """The measured baselines from the last re-lock, or ``None`` if not yet locked.
    The validation-data builders fold these into their JSON when present."""
    if _OUT.exists():
        try:
            return json.loads(_OUT.read_text())
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _summary(scores, labels, ba, bb, *, harness: str, scorer: str) -> dict:
    """Pooled AUC + source-disjoint (mean ± sd) Cllr/AUC for one baseline scorer."""
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=float)
    folds = summarize_folds(barrel_disjoint_folds(scores, labels, np.asarray(ba), np.asarray(bb)))
    out = {
        "scorer": scorer,
        "harness": harness,
        "pooled_auc": round(float(roc_auc(scores, labels)), 4),
        "n_pairs": int(len(scores)),
        "n_km": int((labels == 1).sum()),
    }
    if folds:
        out.update(
            {
                "sd_cllr": round(folds["cllr_mean"], 4),
                "sd_cllr_sd": round(folds["cllr_std"], 4),
                "sd_auc": round(folds["auc_mean"], 4),
                "n_folds": folds["n_folds"],
            }
        )
    return out


def _cartridge() -> dict:
    """Fadul slide-disjoint: naive areal CCF and the cmcR CMC specialist."""
    try:
        from verity.baselines.cmc import cmc_scores
        from verity.examples.cartridge_cmc_proof import _aligned
        from verity.examples.cartridge_fadul import DEFAULT_CACHE, fetch_fadul, load_marks
    except Exception as exc:  # noqa: BLE001 - report, never fabricate
        return {"error": f"import failed: {exc}"}
    masked = fetch_fadul()
    if masked is None:
        return {"error": "Fadul scans unavailable (needs cartridgeCaseScans cache / network)"}
    cmc_rows = cmc_scores(masked, DEFAULT_CACHE)
    if not cmc_rows:
        return {"error": "cmcR baseline unavailable (needs R + cmcR)"}
    v, c, y, ga, gb = _aligned(load_marks(masked), cmc_rows)
    return {
        "split": "slide-disjoint",
        "global_areal_ccf": _summary(
            v,
            y,
            ga,
            gb,
            harness="verity-cartridge-cmc-proof",
            scorer="areal_score (2-D CCF over a rotation grid)",
        ),
        "cmcR": _summary(
            c,
            y,
            ga,
            gb,
            harness="verity-cartridge-cmc-proof",
            scorer="cmcR congruent matching cells (R)",
        ),
    }


def _toolmark_global() -> dict:
    """tmaRks edge-disjoint: the same-pipeline global 1-D CCF (align_1d)."""
    try:
        from verity.examples.toolmark_tmaRks import export_tmaRks, load_tmaRks_marks
        from verity.examples.toolmark_transfer import evaluate
    except Exception as exc:  # noqa: BLE001
        return {"error": f"import failed: {exc}"}
    if not export_tmaRks():
        return {"error": "tmaRks unavailable (needs cache / R+network on first fetch)"}
    res = evaluate(load_tmaRks_marks(level="edge"))
    folds = summarize_folds(res["folds"])
    out = {
        "scorer": "align_1d (1-D CCF; same pipeline as bullets)",
        "harness": "verity-toolmark-tmaRks",
        "dataset": "tmaRks (tool-edge)",
        "split": "edge-disjoint",
        "pooled_auc": round(float(roc_auc(res["scores"], res["labels"])), 4),
        "n_pairs": int(len(res["scores"])),
        "n_km": int(np.asarray(res["labels"]).sum()),
    }
    if folds:
        out.update(
            {
                "sd_cllr": round(folds["cllr_mean"], 4),
                "sd_cllr_sd": round(folds["cllr_std"], 4),
                "sd_auc": round(folds["auc_mean"], 4),
                "n_folds": folds["n_folds"],
            }
        )
    return out


def _toolmark_chumbley() -> dict:
    """ameslab tool-disjoint: the same-pipeline global CCF and the Chumbley U specialist."""
    try:
        from verity.baselines.chumbley import chumbley_scores
        from verity.examples.toolmark_ameslab import (
            DEFAULT_CACHE,
            export_ameslab,
            load_ameslab_marks,
        )
        from verity.examples.toolmark_chumbley_proof import _aligned_arrays
    except Exception as exc:  # noqa: BLE001
        return {"error": f"import failed: {exc}"}
    if not export_ameslab():
        return {"error": "ameslab unavailable (needs R + toolmaRk)"}
    chum = chumbley_scores(DEFAULT_CACHE)
    if not chum:
        return {"error": "Chumbley baseline unavailable (needs R + toolmaRk)"}
    v, c, y, ta, tb = _aligned_arrays(load_ameslab_marks(), chum)
    return {
        "split": "tool-disjoint",
        "dataset": "ameslab (7 tools; proof-of-concept, distinct from tmaRks)",
        "global_1d_ccf": _summary(
            v,
            y,
            ta,
            tb,
            harness="verity-toolmark-chumbley-proof",
            scorer="align_1d (1-D CCF)",
        ),
        "chumbley": _summary(
            c,
            y,
            ta,
            tb,
            harness="verity-toolmark-chumbley-proof",
            scorer="toolmaRk chumbley_non_random U (R)",
        ),
    }


def build(write: bool = True) -> dict:
    payload = {
        "measured_at": date.today().isoformat(),
        "git_commit": git_short_hash(),
        "requires": "~/.cache/verity/{cartridgeCaseScans,tmaRks,ameslab} + R (cmcR, toolmaRk)",
        "note": (
            "Measured comparison baselines for the CMR validation figures/tables, re-lockable "
            "via `verity-relock-baselines`. The deployed CMR numbers live with each reference; "
            "these are the naive and specialist baselines those reductions are compared against."
        ),
        "cartridge": _cartridge(),
        "toolmark_tmaRks_global": _toolmark_global(),
        "toolmark_chumbley_ameslab": _toolmark_chumbley(),
    }
    print(json.dumps(payload, indent=2))
    if write:
        _OUT.parent.mkdir(parents=True, exist_ok=True)
        _OUT.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"\nWROTE {_OUT}")
    return payload


def main() -> None:
    build(write=True)


if __name__ == "__main__":
    main()
