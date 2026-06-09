"""Regenerate the tmaRks toolmark (striated, 1-D) reference — the *deployed* CMR-1D
scorer on the full CSAFE/tmaRks consecutively-manufactured screwdriver set, with
tool-edge cluster IDs and a provenance sidecar.

This completes the CMR table's 1-D side beyond bullets: the SAME congruent-matching-
regions consensus count that scores cartridge breech-face cells (2-D / Song's CMC) here
scores screwdriver striae (1-D / Chumbley's consecutive matching striae), source-disjoint
by the *mark-generating tool edge*, with zero firearms-specific tuning. It is scored under
the SAME ``DEFAULT_SCORER_CONFIG`` as the cartridge reference — so the two share a
``scorer_config_hash``, evidence that one algorithm + one config spans both modalities.

KM = same tool-edge; KNM = different edges. Fully enumerated over all pairs -> deterministic.

    cd services/engine && uv run python -m verity.examples.build_toolmark_reference [--write]

Data: heike/tmaRks ``data/toolmarks.rda`` (MIT), fetched + cached by
:mod:`verity.examples.toolmark_tmaRks` (needs R + network on the first fetch only;
reuses the cache thereafter).
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np

from verity.cmr import cmr_score_1d
from verity.decision import DEFAULT_SCORER_CONFIG

from ._reference_io import write_reference
from .toolmark_tmaRks import export_tmaRks, load_tmaRks_marks

_CFG = DEFAULT_SCORER_CONFIG

_ROOT = Path(__file__).resolve().parents[4]
_OUT = _ROOT / "services/api/verity_api/references/toolmark_tmaRks.npz"


def build() -> dict:
    if not export_tmaRks():
        print("Could not fetch tmaRks — needs R (Rscript) + network on the first run.")
        return {}
    marks = load_tmaRks_marks(level="edge")  # source = tool-edge: the mark generator
    scores: list[float] = []
    labels: list[int] = []
    clusters: list[str] = []
    for (edge_a, _ta, sig_a), (edge_b, _tb, sig_b) in combinations(marks, 2):
        # The DEPLOYED CMR-1D scorer: count of congruent matching regions (cmr-1d) — the
        # same consensus count as cartridge cells, under the same scorer config.
        scores.append(
            float(cmr_score_1d(sig_a, sig_b, corr_thresh=_CFG.cmr_1d_corr, lag_tol=_CFG.cmr_1d_lag))
        )
        labels.append(1 if edge_a == edge_b else 0)
        clusters.append("|".join(sorted((str(edge_a), str(edge_b)))))

    art = write_reference(
        _OUT,
        scores=np.asarray(scores),
        labels=np.asarray(labels),
        cluster_ids=clusters,
        name="tmaRks screwdriver toolmarks (consecutively manufactured; tool-edge sources)",
        generator="build_toolmark_reference",
        seed=None,
        datasets=[
            {
                "external_id": "tmaRks-toolmarks",
                "tag": "tmaRks",
                "source": "heike/tmaRks data/toolmarks.rda (MIT)",
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
