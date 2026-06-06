"""Phase 4 head-to-head: Verity vs the Chumbley toolmark specialist.

The toolmark analog of the bulletxtrctr firearms proof. Both systems score the
*same* Ames Lab screwdriver-mark pairs and are split the *same* way (source-
disjoint by tool); each calibrates its own score→LR (the shared, ELUB-bounded
``ScoreLRModel``) on the train tools and is scored on the held-out ones:

* **Verity** — the domain-general pipeline: ``profile_signature`` (1-D form
  removal + roughness isolation) → ``align_1d`` cross-correlation. No toolmark-
  specific engineering; the same code that did bullet lands.
* **Chumbley** — ``toolmaRk::chumbley_non_random``'s U statistic, the hand-built
  specialist (the analog of bulletxtrctr's random forest).

The claim mirrors the firearms proof: a transparent, domain-general pipeline
reaches comparable discrimination/``Cllr`` to the specialist on its home turf —
now in a *non-firearm* domain it was never tuned for. (Small data: a proof-of-
concept.)  Requires R with ``toolmaRk``.  Run::

    uv run verity-toolmark-chumbley-proof
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import align_1d, roc_auc
from verity.baselines.chumbley import chumbley_scores
from verity.examples.hamby_validation import barrel_disjoint_folds
from verity.examples.toolmark_ameslab import DEFAULT_CACHE, export_ameslab, load_ameslab_marks


def verity_pair_scores(marks) -> dict:
    """``(i, j)`` (0-indexed, i<j) → ``(ccf, label, tool_i, tool_j)``."""
    out = {}
    for (ia, (sa, _na, siga)), (ib, (sb, _nb, sigb)) in combinations(enumerate(marks), 2):
        out[(ia, ib)] = (align_1d(siga, sigb)[1], 1 if sa == sb else 0, sa, sb)
    return out


def _aligned_arrays(marks, chumbley):
    """Join Verity and Chumbley on the same pairs; drop any with a non-finite
    score on either side. Returns Verity scores, Chumbley scores, labels, tools."""
    vpairs = verity_pair_scores(marks)
    v, c, y, ta, tb = [], [], [], [], []
    for row in chumbley:
        key = (int(row["i"]), int(row["j"]))
        if key not in vpairs:
            continue
        cc, label, tool_a, tool_b = vpairs[key]
        u = row["U"]
        if u in ("NA", ""):
            continue
        u = float(u)
        if not (np.isfinite(cc) and np.isfinite(u)):
            continue
        v.append(cc)
        c.append(u)
        y.append(label)
        ta.append(tool_a)
        tb.append(tool_b)
    return (np.array(v), np.array(c), np.array(y), np.array(ta), np.array(tb))


def _fold_stats(folds, key):
    return np.array([f[key] for f in folds]) if folds else np.array([np.nan])


def _print(tag, scores, labels, folds):
    c = _fold_stats(folds, "cllr")
    cm = _fold_stats(folds, "cllr_min")
    au = _fold_stats(folds, "auc")
    print(
        f"  {tag:20s} overallAUC={roc_auc(scores, labels):.3f}  "
        f"Cllr={c.mean():.3f}+/-{c.std():.3f}  Cllr_min={cm.mean():.3f}  "
        f"AUC={au.mean():.3f}  calib-loss={c.mean() - cm.mean():+.3f}"
    )


def main() -> None:
    if not export_ameslab():
        print("Could not load ameslab — install R with 'toolmaRk' (install.packages('toolmaRk')).")
        return
    chumbley = chumbley_scores(DEFAULT_CACHE)
    if not chumbley:
        print("Could not score Chumbley baseline — R / toolmaRk unavailable.")
        return
    marks = load_ameslab_marks()
    v, c, y, ta, tb = _aligned_arrays(marks, chumbley)

    print("Phase 4 head-to-head — Verity (CCF+LR) vs Chumbley (U), source-disjoint by tool:")
    print(
        f"  pairs={len(y)}  KM={int(y.sum())}  KNM={int((y == 0).sum())}  "
        f"tools={len(set(ta.tolist()) | set(tb.tolist()))}\n"
    )
    v_folds = barrel_disjoint_folds(v, y, ta, tb)
    c_folds = barrel_disjoint_folds(c, y, ta, tb)
    _print("Verity (CCF+LR)", v, y, v_folds)
    _print("Chumbley (U)", c, y, c_folds)
    dv = _fold_stats(v_folds, "cllr").mean()
    dc = _fold_stats(c_folds, "cllr").mean()
    verdict = "matches/beats" if dv <= dc + 0.05 else "trails"
    print(f"\n  -> Verity {verdict} the Chumbley specialist on Cllr ({dv:.3f} vs {dc:.3f})")
    print(
        "  NOTE: 16 profiles / 7 tools / 15 KM pairs (one dominant), cross-angle KM —\n"
        "  a small, hard proof-of-concept, not a definitive number."
    )


if __name__ == "__main__":
    main()
