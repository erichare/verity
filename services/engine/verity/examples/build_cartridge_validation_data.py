"""Persist the Fadul cartridge-case (impressed) validation numbers the white paper
quotes — the source of truth behind the impressed row and ``fig_cllr_cartridge``.

The **deployed CMR-2D** numbers are recomputed here from the *committed* reference
``cartridge_fadul.npz`` (no network): in-sample AUC / Cllr / Cllr_min and the
slide-disjoint summary. The two comparison **baselines** — the naive global areal-CCF
score and the cmcR Congruent Matching Cells specialist — are read from
``baselines.json`` (measured + re-lockable via ``verity-relock-baselines``, which needs
git + network + R). If baselines haven't been locked yet, the baseline numbers are
emitted as ``null`` rather than fabricated.

    cd services/engine && uv run verity-cartridge-validation-data
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
_REF = _ROOT / "services/api/verity_api/references/cartridge_fadul.npz"
_OUT = _ROOT / "docs/whitepaper/data/cartridge_fadul.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline(measured: dict | None, *, method: str, scorer: str, note: str) -> dict:
    """A figure/table baseline entry: pooled AUC + slide-disjoint Cllr (± sd) from the
    measured ``baselines.json``, or ``null`` numbers if the baselines aren't locked yet."""
    m = measured or {}
    return {
        "method": method,
        "scorer": scorer,
        "auc": m.get("pooled_auc"),
        "cllr": m.get("sd_cllr"),
        "cllr_sd": m.get("sd_cllr_sd"),
        "measured_by": "verity-relock-baselines",
        "measured": bool(m),
        "reproducible": False,  # needs R + caches to re-lock; not offline from the committed npz
        "note": note,
    }


def build(write: bool = True) -> dict:
    """Compute the impressed validation payload from the committed reference (+ measured
    baselines) and (optionally) write ``docs/whitepaper/data/cartridge_fadul.json``."""
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
    cart_bl = (load_baselines() or {}).get("cartridge", {})

    # The three-method comparison the figure draws: naive areal -> generic CMR-2D ->
    # CMC specialist. AUC is pooled (one basis for all three); Cllr is slide-disjoint
    # (this work's honest cost). The CMR-2D row is reproducible from the npz; the two
    # baselines are measured by verity-relock-baselines.
    methods = [
        _baseline(
            cart_bl.get("global_areal_ccf"),
            method="global areal CCF",
            scorer="areal_score (2-D cross-correlation over a rotation grid)",
            note="the pre-CMR baseline: one global areal correlation, no congruence consensus",
        ),
        {
            "method": "CMR-2D (deployed)",
            "scorer": "cmr_count — areal_votes -> consensus_members (Verity, generic)",
            "auc": round(summary.auc, 4),
            "cllr": round(bd.get("cllr_mean"), 4) if bd else None,
            "cllr_sd": round(bd.get("cllr_std"), 4) if bd else None,
            "measured_by": "verity-cartridge-validation-data",
            "reproducible": True,
            "note": "no cartridge-specific engineering — same CMR algorithm as bullets/toolmarks",
        },
        _baseline(
            cart_bl.get("cmcR"),
            method="cmcR (CMC specialist)",
            scorer="cmcR congruent matching cells (run via R)",
            note="the field-standard impressed-mark method; the target CMR-2D should approach",
        ),
    ]

    payload = {
        "reference": summary.reference_name,
        "domain": "impressed",
        "deployed_scorer": "CMR-2D (congruent matching regions, 2-D cells + rotation)",
        "reproducible_from": "services/api/verity_api/references/cartridge_fadul.npz",
        "baselines_from": "docs/whitepaper/data/baselines.json (verity-relock-baselines)",
        "summary": summary.to_dict(),
        "methods": methods,
        "provenance": {
            "generator": "build_cartridge_validation_data",
            "git_commit": git_short_hash(),
            "source_reference_sha256": _sha256(_REF),
            "generated_at": summary.generated_at,
            "note": (
                "Deployed CMR-2D numbers recomputed from the committed reference (no network). "
                "Baselines read from baselines.json (re-lock via verity-relock-baselines)."
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
    if not cart_bl:
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
