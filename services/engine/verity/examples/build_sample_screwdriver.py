"""Generate the homepage 'Load a sample' card from a REAL screwdriver-toolmark comparison.

A fixed, representative same-tool-edge tmaRks pair, scored with the deployed CMR-1D scorer
and calibrated against the committed toolmark reference — the same third CMR reduction the
white paper reports. Written to ``services/web/lib/sample-screwdriver.json`` so the homepage
sample is real and reproducible from the committed reference + the tmaRks cache (no network).

    cd services/engine && uv run verity-build-sample-screwdriver
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from verity.cmr import cmr_score_1d
from verity.decision import DEFAULT_SCORER_CONFIG
from verity.examples.toolmark_tmaRks import export_tmaRks, load_tmaRks_marks
from verity.report import build_comparison_report

_CFG = DEFAULT_SCORER_CONFIG
_ROOT = Path(__file__).resolve().parents[4]
_REF = _ROOT / "services/api/verity_api/references/toolmark_tmaRks.npz"
_OUT = _ROOT / "services/web/lib/sample-screwdriver.json"

# A fixed same-tool-edge, same-condition (F80) pair — a textbook same-source toolmark
# comparison. Deterministic, not cherry-picked: every clean same-edge pair scores similarly.
_PAIR = ("T01SB-F80-01", "T01SB-F80-02")


def build(write: bool = True) -> dict:
    if not export_tmaRks():
        raise SystemExit("tmaRks cache (or R + network on first fetch) required")
    marks = {tid: sig for _edge, tid, sig in load_tmaRks_marks(level="edge")}
    if not (_PAIR[0] in marks and _PAIR[1] in marks):
        raise SystemExit(f"pair {_PAIR} not found in tmaRks marks")
    score = float(
        cmr_score_1d(
            marks[_PAIR[0]], marks[_PAIR[1]], corr_thresh=_CFG.cmr_1d_corr, lag_tol=_CFG.cmr_1d_lag
        )
    )
    ref = np.load(_REF, allow_pickle=False)
    clusters = ref["cluster_ids"] if "cluster_ids" in ref.files else None
    rep = build_comparison_report(
        score=score,
        reference_scores=ref["scores"],
        reference_labels=ref["labels"],
        domain="striated-toolmark",
        reference_name="tmaRks screwdriver toolmarks",
        score_kind="cmr-1d",
        ci=True,
        ci_clusters=clusters,
    ).to_dict()
    card = {
        "domain": rep["domain"],
        "score": rep["score"],
        "score_kind": rep["score_kind"],
        "likelihood_ratio": rep["likelihood_ratio"],
        "log10_lr": rep["log10_lr"],
        "log10_lr_ci_lo": rep["log10_lr_ci_lo"],
        "log10_lr_ci_hi": rep["log10_lr_ci_hi"],
        # n_sources omitted: the clustered bootstrap counts pair-source-set clusters, which
        # overstates independent sources (56 tool edges), so we don't surface it on the card.
        "verbal": rep["verbal"],
        "lr_bound_log10": rep["lr_bound_log10"],
        "reference": rep["reference"],
        "pair": list(_PAIR),
        "scope_note": (
            "A precomputed sample — a real same-tool-edge tmaRks screwdriver comparison, scored "
            "with CMR-1D and calibrated on the committed toolmark reference. Not a claim about the "
            "error rate of examination, which remains unknown."
        ),
    }
    print(
        f"screwdriver sample: {_PAIR[0]} vs {_PAIR[1]}  cmr_count={score:.0f}  "
        f"LR={card['likelihood_ratio']:,.1f}  log10={card['log10_lr']:.2f}  {card['verbal']}"
    )
    if write:
        _OUT.write_text(json.dumps(card, indent=2) + "\n")
        print(f"WROTE {_OUT}")
    return card


def main() -> None:
    build(write=True)


if __name__ == "__main__":
    main()
