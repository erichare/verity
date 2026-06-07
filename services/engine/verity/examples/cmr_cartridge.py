"""Congruent Matching Regions on Fadul cartridge cases — the 2-D / CMC instantiation.

Runs the *generic* CMR scorer (``verity.cmr.cmr_score_2d`` — the same algorithm,
parameterized to 2-D cells + translation/rotation) on the Fadul breech-face set,
source-disjoint by slide. The question: does CMR — Verity's own code, no cmcR —
move from the global-CCF areal baseline (AUC 0.91, Cllr 0.53) toward the cmcR
specialist (AUC 1.00, Cllr 0.19)? CMR-2D *is* CMC, so it should.

Run::  uv run verity-cmr-cartridge
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import cllr_min, roc_auc
from verity.cmr import cmr_score_2d
from verity.examples.cartridge_fadul import fetch_fadul, load_marks
from verity.examples.hamby_validation import barrel_disjoint_folds


def main() -> None:
    masked = fetch_fadul()
    if masked is None:
        print("Could not fetch Fadul scans — needs git + network.")
        return
    marks = load_marks(masked)
    scores, labels, sa, sb = [], [], [], []
    for (slide_a, _na, sig_a), (slide_b, _nb, sig_b) in combinations(marks, 2):
        scores.append(float(cmr_score_2d(sig_a, sig_b)))
        labels.append(1 if slide_a == slide_b else 0)
        sa.append(slide_a)
        sb.append(slide_b)
    scores, labels = np.array(scores), np.array(labels)
    folds = barrel_disjoint_folds(scores, labels, np.array(sa), np.array(sb))

    print("Congruent Matching Regions (CMR-2D) on Fadul cartridge cases, slide-disjoint:")
    print(f"  {len(marks)} scans  pairs={len(scores)} KM={int(labels.sum())}")
    km, knm = scores[labels == 1], scores[labels == 0]
    print(f"  CMR count: KM mean={km.mean():.1f}  KNM mean={knm.mean():.1f}")
    print(f"  pooled AUC={roc_auc(scores, labels):.3f}  Cllr_min={cllr_min(scores, labels):.3f}")
    if folds:
        c = np.array([f["cllr"] for f in folds])
        au = np.array([f["auc"] for f in folds])
        cm = np.array([f["cllr_min"] for f in folds])
        print(f"  slide-disjoint: Cllr={c.mean():.3f}+/-{c.std():.3f} "
              f"Cllr_min={cm.mean():.3f} AUC={au.mean():.3f}")
    print("\n  Compare: global areal CCF AUC 0.91/Cllr 0.53  |  cmcR (CMC) AUC 1.00/Cllr 0.19")


if __name__ == "__main__":
    main()
