"""Persist the Fadul cartridge-case (impressed) validation numbers the white paper
quotes — the source of truth behind the impressed row and ``fig_cllr_cartridge``.

The **deployed CMR-2D** numbers are recomputed here from the *committed* reference
``cartridge_fadul.npz`` (no network): in-sample AUC / Cllr / Cllr_min and the
slide-disjoint summary (mean ± sd over folds, no slide spanning train and test). The
two comparison **baselines** — the naive global areal-CCF score and the cmcR Congruent
Matching Cells specialist — are *recorded* results from the named harnesses (which need
git + network and, for cmcR, R), not recomputed here; each is flagged ``reproducible``
so a reader knows exactly what reproduces offline.

    cd services/engine && uv run verity-cartridge-validation-data
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from verity.report_validation import compute_validation_summary

from ._reference_io import barrels_from_clusters, git_short_hash, load_reference

_ROOT = Path(__file__).resolve().parents[4]
_REF = _ROOT / "services/api/verity_api/references/cartridge_fadul.npz"
_OUT = _ROOT / "docs/whitepaper/data/cartridge_fadul.json"

# Recorded comparison baselines on the SAME slide-disjoint Fadul task. These need
# git + network (and R + cmcR for the specialist), so they are recorded from the named
# harnesses rather than recomputed from the committed reference. Re-lock them with the
# commands below before a paper revision.
_BASELINES = [
    {
        "method": "global areal CCF",
        "scorer": "areal_score (2-D cross-correlation over a rotation grid)",
        "auc": 0.91,
        "cllr": 0.53,
        "measured_by": "verity-cmr-cartridge",
        "requires": "git+network",
        "reproducible": False,
        "note": "the pre-CMR baseline: a single global areal correlation, no congruence consensus",
    },
    {
        "method": "cmcR (CMC specialist)",
        "scorer": "cmcR congruent matching cells (run via R, as a competitor only)",
        "auc": 1.00,
        "cllr": 0.19,
        "measured_by": "verity-cartridge-cmc-proof",
        "requires": "git+network+R(cmcR)",
        "reproducible": False,
        "note": "the field-standard impressed-mark method; the target CMR-2D should approach",
    },
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(write: bool = True) -> dict:
    """Compute the impressed validation payload from the committed reference and
    (optionally) write ``docs/whitepaper/data/cartridge_fadul.json``."""
    ref = load_reference(_REF)
    barrels_a, barrels_b = barrels_from_clusters(ref.cluster_ids)
    summary = compute_validation_summary(
        ref.scores,
        ref.labels,
        reference_name=(ref.provenance or {}).get("name", "Fadul cartridge cases"),
        domain="impressed",
        barrels_a=barrels_a,
        barrels_b=barrels_b,
        generated_at=date.today().isoformat(),
    )
    bd = summary.barrel_disjoint or {}

    # The three-method comparison the figure draws: naive areal -> generic CMR-2D ->
    # CMC specialist. The CMR-2D row is reproducible from the npz; AUC is pooled (so all
    # three are on one basis), Cllr is the slide-disjoint cost (this work's honest claim).
    methods = [
        _BASELINES[0],
        {
            "method": "CMR-2D (deployed)",
            "scorer": "cmr_count — areal_votes -> consensus_members (Verity, generic)",
            "auc": round(summary.auc, 4),
            "cllr": round(bd.get("cllr_mean", summary.cllr), 4),
            "cllr_sd": round(bd.get("cllr_std", 0.0), 4),
            "measured_by": "verity-cartridge-validation-data",
            "requires": "none (committed reference)",
            "reproducible": True,
            "note": "no cartridge-specific engineering — same CMR algorithm as bullets/toolmarks",
        },
        _BASELINES[1],
    ]

    payload = {
        "reference": summary.reference_name,
        "domain": "impressed",
        "deployed_scorer": "CMR-2D (congruent matching regions, 2-D cells + rotation)",
        "reproducible_from": "services/api/verity_api/references/cartridge_fadul.npz",
        "summary": summary.to_dict(),
        "methods": methods,
        "provenance": {
            "generator": "build_cartridge_validation_data",
            "git_commit": git_short_hash(),
            "source_reference_sha256": _sha256(_REF),
            "generated_at": summary.generated_at,
            "note": (
                "Deployed CMR-2D numbers recomputed from the committed reference (no network). "
                "Baselines are recorded results from the named harnesses; recompute with "
                "git+network (and R + cmcR for the specialist) before a paper revision."
            ),
        },
    }

    bd_txt = (
        f"slide-disjoint Cllr={bd['cllr_mean']:.3f}±{bd['cllr_std']:.3f} "
        f"AUC={bd['auc_mean']:.3f}±{bd['auc_std']:.3f}"
        if bd
        else "slide-disjoint: too few slides"
    )
    print(
        f"impressed (Fadul, CMR-2D): n_km={summary.n_km} n_knm={summary.n_knm} "
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
