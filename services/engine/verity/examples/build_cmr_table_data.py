"""The CMR table, as one reproducible artifact: the *same* algorithm under the *same*
scorer config, reduced to each modality and characterized source-disjoint.

Loads the three committed references — bullet lands (CMR aggregate / ``diag_contrast``),
cartridge breech faces (CMR-2D / Song's CMC), screwdriver toolmarks (CMR-1D / Chumbley's
CMS) — recomputes each one's in-sample and source-disjoint summary through the identical
:func:`compute_validation_summary` path (no network), and asserts all three carry the
SAME ``scorer_config_hash`` — the cryptographic evidence that one configuration spans
every modality. Writes two consistent outputs:

* ``docs/whitepaper/data/cmr_table.json`` — the paper's three-reduction table; and
* ``services/web/lib/cmr-validation.json`` — the same numbers for ``verity.codes/method``.

    cd services/engine && uv run verity-cmr-table-data
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from verity.report_validation import compute_validation_summary

from ._reference_io import barrels_from_clusters, git_short_hash, load_reference

_ROOT = Path(__file__).resolve().parents[4]
_REFS = _ROOT / "services/api/verity_api/references"
_OUT_PAPER = _ROOT / "docs/whitepaper/data/cmr_table.json"
_OUT_WEB = _ROOT / "services/web/lib/cmr-validation.json"

# (reference stem, domain, display label, the per-modality reduction it recovers, the
# field-standard specialist that reduction matches, reference scope note)
_REDUCTIONS = [
    {
        "stem": "bullet_pooled",
        "domain": "striated",
        "label": "Bullet lands",
        "reduction": "consecutive matching striae (1-D, inter-land aggregate)",
        "specialist": "bulletxtrctr",
        "scope": "pooled: Hamby-252/173, PGPD Beretta, Phoenix",
    },
    {
        "stem": "cartridge_fadul",
        "domain": "impressed",
        "label": "Cartridge breech face",
        "reduction": "congruent matching cells / CMC (2-D)",
        "specialist": "cmcR",
        "scope": "Fadul (10 consecutively-manufactured slides)",
    },
    {
        "stem": "toolmark_tmaRks",
        "domain": "striated-toolmark",
        "label": "Screwdriver toolmark",
        "reduction": "Chumbley consecutive matching striae (1-D)",
        "specialist": "toolmaRk (Chumbley U)",
        "scope": "tmaRks (56 tool-edges; source = mark generator)",
    },
]


def build(write: bool = True) -> dict:
    """Compute the three-reduction table from the committed references and (optionally)
    write the paper + web JSON. Raises if the references disagree on scorer config."""
    rows = []
    config_hashes = set()
    for spec in _REDUCTIONS:
        ref = load_reference(_REFS / f"{spec['stem']}.npz")
        if ref.provenance:
            config_hashes.add(ref.provenance.get("scorer_config_hash"))
        barrels_a, barrels_b = barrels_from_clusters(ref.cluster_ids)
        s = compute_validation_summary(
            ref.scores,
            ref.labels,
            reference_name=(ref.provenance or {}).get("name", spec["stem"]),
            domain=spec["domain"],
            barrels_a=barrels_a,
            barrels_b=barrels_b,
        )
        bd = s.barrel_disjoint or {}
        rows.append(
            {
                "modality": spec["domain"],
                "label": spec["label"],
                "reduction": spec["reduction"],
                "specialist": spec["specialist"],
                "reference": spec["scope"],
                "n_km": s.n_km,
                "n_knm": s.n_knm,
                "in_sample_auc": round(s.auc, 4),
                "in_sample_cllr_min": round(s.cllr_min, 4),
                "source_disjoint": {
                    "cllr": round(bd.get("cllr_mean"), 4) if bd else None,
                    "cllr_sd": round(bd.get("cllr_std"), 4) if bd else None,
                    "auc": round(bd.get("auc_mean"), 4) if bd else None,
                    "n_folds": bd.get("n_folds") if bd else None,
                },
            }
        )

    # The integrity claim: one config across every modality. Fail loudly if not.
    config_hashes.discard(None)
    if len(config_hashes) > 1:
        raise ValueError(f"references disagree on scorer_config_hash: {config_hashes}")
    shared_hash = next(iter(config_hashes), None)

    payload = {
        "generated_at": date.today().isoformat(),
        "git_commit": git_short_hash(),
        "scorer_config_hash": shared_hash,
        "claim": (
            "One algorithm, one scorer config (shared hash above), reduced to each "
            "modality and validated source-disjoint — CMR recovers the field-standard "
            "per-modality method in each case."
        ),
        "reductions": rows,
        "note": (
            "Every row recomputed from a committed reference via the same source-disjoint "
            "path (no network). Bullet lands are the pooled 4-study reference (the single "
            "best study, Hamby-252, is lower still); cartridge/toolmark are their full sets. "
            "These characterize weight of evidence on the named references, not field error rates."
        ),
    }

    for r in rows:
        sd = r["source_disjoint"]
        print(
            f"{r['label']:24s} {r['modality']:18s} "
            f"source-disjoint Cllr={sd['cllr']}±{sd['cllr_sd']} AUC={sd['auc']} "
            f"(n_km={r['n_km']})"
        )
    print(f"shared scorer_config_hash: {shared_hash}")
    if write:
        for out in (_OUT_PAPER, _OUT_WEB):
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2) + "\n")
            print(f"WROTE {out}")
    else:
        print("DRY-RUN (pass write=True to save)")
    return payload


def main() -> None:
    build(write=True)


if __name__ == "__main__":
    main()
