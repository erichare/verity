"""Phase 4 head-to-head: Verity (areal) vs the Congruent Matching Cells specialist.

The cartridge-case analog of the bulletxtrctr (bullets) and Chumbley (toolmarks)
proofs, and the test of the striated->impressed crossing against the field's
standard impressed-mark method. Both systems score the *same* Fadul cartridge-case
pairs and split the *same* way (slide-disjoint); each calibrates its own score->LR
with the shared, ELUB-bounded ``ScoreLRModel``:

* **Verity** — :func:`verity.areal.areal_score`: the same form-removal + roughness
  isolation as bullet lands, then 2-D cross-correlation over a rotation grid. No
  cartridge-specific engineering.
* **CMC** — ``cmcR``'s Congruent Matching Cells count (the specialist), run via R
  as a competitor only.

Requires R with ``cmcR`` for the baseline.  Run::

    uv run verity-cartridge-cmc-proof
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import roc_auc
from verity.areal import areal_score
from verity.baselines.cmc import cmc_scores
from verity.examples.cartridge_fadul import DEFAULT_CACHE, fetch_fadul, load_marks
from verity.examples.hamby_validation import barrel_disjoint_folds


def _aligned(marks, cmc_rows):
    """Join Verity areal scores and CMC counts on the same (i, j) pairs; drop any
    with a non-finite score on either side."""
    vmap = {}
    for (ia, (slide_a, _na, sig_a)), (ib, (slide_b, _nb, sig_b)) in combinations(
        enumerate(marks), 2
    ):
        vmap[(ia, ib)] = (areal_score(sig_a, sig_b), 1 if slide_a == slide_b else 0,
                          slide_a, slide_b)
    v, c, y, ga, gb = [], [], [], [], []
    for row in cmc_rows:
        key = (int(row["i"]), int(row["j"]))
        if key not in vmap:
            continue
        vscore, label, slide_a, slide_b = vmap[key]
        if slide_a != int(row["slide_i"]) or slide_b != int(row["slide_j"]):
            continue  # ordering mismatch guard
        cmc = row["cmc"]
        if cmc in ("NA", ""):
            continue
        v.append(vscore)
        c.append(float(cmc))
        y.append(label)
        ga.append(slide_a)
        gb.append(slide_b)
    return (np.array(v), np.array(c), np.array(y), np.array(ga), np.array(gb))


def _fold(folds, key):
    return np.array([f[key] for f in folds]) if folds else np.array([np.nan])


def _print(tag, scores, labels, folds):
    c, cm, au = (_fold(folds, k) for k in ("cllr", "cllr_min", "auc"))
    print(
        f"  {tag:16s} overallAUC={roc_auc(scores, labels):.3f}  "
        f"Cllr={c.mean():.3f}+/-{c.std():.3f}  Cllr_min={cm.mean():.3f}  "
        f"AUC={au.mean():.3f}  calib-loss={c.mean() - cm.mean():+.3f}"
    )


def main() -> None:
    masked = fetch_fadul()
    if masked is None:
        print("Could not fetch Fadul scans — needs git + network.")
        return
    marks = load_marks(masked)
    cmc_rows = cmc_scores(masked, DEFAULT_CACHE)
    if not cmc_rows:
        print("Could not score CMC baseline — needs R + cmcR (install_github CSAFE-ISU/cmcR).")
        return
    v, c, y, ga, gb = _aligned(marks, cmc_rows)
    print("Phase 4 head-to-head — Verity (areal CCF+LR) vs CMC (cmcR), slide-disjoint:")
    print(f"  pairs={len(y)}  KM={int(y.sum())}  KNM={int((y == 0).sum())}  "
          f"slides={len(set(ga.tolist()) | set(gb.tolist()))}\n")
    v_folds = barrel_disjoint_folds(v, y, ga, gb)
    c_folds = barrel_disjoint_folds(c, y, ga, gb)
    _print("Verity (areal)", v, y, v_folds)
    _print("CMC (cmcR)", c, y, c_folds)
    dv, dc = _fold(v_folds, "cllr").mean(), _fold(c_folds, "cllr").mean()
    verdict = "matches/beats" if dv <= dc + 0.05 else "trails"
    print(f"\n  -> Verity {verdict} the CMC specialist on Cllr ({dv:.3f} vs {dc:.3f})")
    print("  NOTE: 10 consecutively-manufactured slides / 10 KM pairs — small,"
          " hardest benchmark; proof-of-concept.")


if __name__ == "__main__":
    main()
