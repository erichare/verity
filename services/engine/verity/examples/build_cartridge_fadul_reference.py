"""Regenerate the Fadul cartridge-case (impressed) reference with *slide* cluster IDs
and a provenance sidecar.

Same data and scoring as ``cartridge_fadul`` (10 consecutively-manufactured slides x 2
cases, areal CCF over a rotation grid), but it also records each pair's slide IDs so the
API can run the clustered bootstrap (resampling whole slides), and writes the provenance.
KM = same slide; KNM = different slides. Fully enumerated → deterministic.

    cd services/engine && uv run python -m verity.examples.build_cartridge_fadul_reference [--write]
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np

from verity.cmr import areal_votes, consensus_members
from verity.decision import DEFAULT_SCORER_CONFIG

from ._reference_io import write_reference
from .cartridge_fadul import fetch_fadul, load_marks

_CFG = DEFAULT_SCORER_CONFIG

_ROOT = Path(__file__).resolve().parents[4]
_OUT = _ROOT / "services/api/verity_api/references/cartridge_fadul.npz"


def build() -> dict:
    masked = fetch_fadul()
    if masked is None:
        print("Could not fetch Fadul scans — needs git + network (CSAFE-ISU/cartridgeCaseScans).")
        return {}
    marks = load_marks(masked)
    scores: list[float] = []
    labels: list[int] = []
    clusters: list[str] = []
    for (slide_a, _na, sig_a), (slide_b, _nb, sig_b) in combinations(marks, 2):
        # The DEPLOYED impressed scorer: count of congruent matching regions (cmr-2d),
        # not areal_score — the reference must be scored exactly as live comparisons are.
        members = consensus_members(
            areal_votes(sig_a, sig_b), corr_thresh=_CFG.cmr_corr, transform_tol=_CFG.cmr_tol
        )
        scores.append(float(len(members)))
        labels.append(1 if slide_a == slide_b else 0)
        clusters.append("|".join(sorted((str(slide_a), str(slide_b)))))

    art = write_reference(
        _OUT,
        scores=np.asarray(scores),
        labels=np.asarray(labels),
        cluster_ids=clusters,
        name="Fadul cartridge cases (10 consecutively-manufactured slides)",
        generator="build_cartridge_fadul_reference",
        seed=None,
        datasets=[
            {
                "external_id": "fadul-cartridge-cases",
                "tag": "Fadul-2011",
                "source": "CSAFE-ISU/cartridgeCaseScans (fadulMasked, CC-BY 4.0)",
            }
        ],
        write="--write" in sys.argv,
    )
    d = art.provenance["diagnostics"]
    print(
        f"n_km={d['n_km']} n_knm={d['n_knm']} n_sources={art.provenance['n_sources']} "
        f"AUC={d['auc']:.3f} Cllr_min={d['cllr_min']:.3f}"
    )
    print(f"{'WROTE' if '--write' in sys.argv else 'DRY-RUN (pass --write to save)'}: {_OUT}")
    return art.provenance


if __name__ == "__main__":
    build()
