"""Best-of-both: fuse the global similarity and the CMR count into one LR.

CMR wins on impressed/partial/warped marks; the global cross-correlation wins on
clean striated marks where the whole mark coheres under one transform. Fusing the
two scores at the calibrated-LR layer takes the better of each *per dataset*,
demonstrated source-disjoint on both an impressed set (Fadul cartridge cases) and
a striated set (ameslab toolmarks):

    fused Cllr <= min(global-only, CMR-only) on BOTH domains.

Run::  uv run verity-cmr-fusion
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import align_1d, roc_auc
from verity.areal import areal_score
from verity.cmr import cmr_score_1d, cmr_score_2d
from verity.decision.metrics import cllr
from verity.decision.score_fusion import FusionLRModel


def _disjoint(feats, labels, ga, gb, *, n_splits=10, test_frac=0.4, seed=0):
    """Mean source-disjoint (test Cllr, test AUC) for a 1- or 2-column feature set."""
    feats = np.asarray(feats, dtype=np.float64)
    if feats.ndim == 1:
        feats = feats[:, None]
    sources = sorted(set(ga.tolist()) | set(gb.tolist()))
    rng = np.random.default_rng(seed)
    n_test = max(2, round(len(sources) * test_frac))
    cl, au = [], []
    for _ in range(n_splits):
        tb = set(rng.permutation(sources)[:n_test].tolist())
        te = np.array([x in tb and y in tb for x, y in zip(ga, gb, strict=True)])
        tr = np.array([x not in tb and y not in tb for x, y in zip(ga, gb, strict=True)])
        if labels[tr].sum() < 3 or labels[te].sum() < 1:
            continue
        lr = FusionLRModel().fit(feats[tr], labels[tr]).predict_lr(feats[te])
        cl.append(cllr(lr[labels[te] == 1], lr[labels[te] == 0]))
        au.append(roc_auc(lr, labels[te]))
    return float(np.mean(cl)), float(np.mean(au))


def _features(name, marks, global_fn, cmr_fn):
    """Per-pair (global, CMR, label, sources), cached — the scores are expensive."""
    from pathlib import Path

    slug = "".join(ch if ch.isalnum() else "_" for ch in name)
    cache = Path.home() / ".cache" / "verity" / f"fusion_{slug}.npz"
    if cache.exists():
        d = np.load(cache, allow_pickle=True)
        return d["g"], d["c"], d["y"], d["ga"], d["gb"]
    g, c, y, ga, gb = [], [], [], [], []
    for (src_a, _na, sig_a), (src_b, _nb, sig_b) in combinations(marks, 2):
        g.append(float(global_fn(sig_a, sig_b)))
        c.append(float(cmr_fn(sig_a, sig_b)))
        y.append(1 if src_a == src_b else 0)
        ga.append(src_a)
        gb.append(src_b)
    g, c, y, ga, gb = (np.array(g), np.array(c), np.array(y), np.array(ga), np.array(gb))
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, g=g, c=c, y=y, ga=ga, gb=gb)
    return g, c, y, ga, gb


def evaluate_domain(name, marks, global_fn, cmr_fn):
    g, c, y, ga, gb = _features(name, marks, global_fn, cmr_fn)
    print(f"\n=== {name}  ({len(marks)} marks, pairs={len(y)}, KM={int(y.sum())}) ===")
    for label, feats in (("global only", g), ("CMR only", c), ("FUSED", np.column_stack([g, c]))):
        cl, au = _disjoint(feats, y, ga, gb)
        print(f"  {label:11s} source-disjoint Cllr={cl:.3f}  AUC={au:.3f}")


def main() -> None:
    # Impressed: Fadul cartridge cases (global areal CCF vs CMR-2D)
    try:
        from verity.examples.cartridge_fadul import fetch_fadul, load_marks

        masked = fetch_fadul()
        if masked is not None:
            evaluate_domain("Fadul cartridge cases (impressed)", load_marks(masked),
                            lambda a, b: areal_score(a, b), lambda a, b: cmr_score_2d(a, b))
    except Exception as exc:  # noqa: BLE001 - the demo degrades if data/R is absent
        print(f"  (cartridge skipped: {exc})")

    # Striated: ameslab toolmarks (global align_1d vs CMR-1D)
    try:
        from verity.examples.toolmark_ameslab import export_ameslab, load_ameslab_marks

        if export_ameslab():
            evaluate_domain("ameslab toolmarks (striated)", load_ameslab_marks(),
                            lambda a, b: align_1d(a, b)[1], lambda a, b: cmr_score_1d(a, b))
    except Exception as exc:  # noqa: BLE001
        print(f"  (toolmarks skipped: {exc})")


if __name__ == "__main__":
    main()
