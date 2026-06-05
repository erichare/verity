"""Phase-2 validation: turn the Phase-1 bullet-comparison scores into calibrated
likelihood ratios and characterize them with a **barrel-disjoint** ``Cllr`` on
Hamby 252.

Splitting by barrel (no barrel in both train and test) is the source-disjoint
discipline whose absence the Cuellar et al. (2024) critique flags. The result is
a weight of evidence with a characterized cost *on a named dataset* — not a
field-wide error-rate claim.

Run after ingesting hamby-252:  ``uv run verity-validate-hamby``
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import ScoreLRModel, cllr, cllr_min, roc_auc
from verity.examples.hamby_km_knm import (
    LAMBDA_C,
    LAMBDA_S,
    ORIENT,
    _catalog_dir,
    bullet_score,
    read_surface,
)
from verity.signature import striation_signature


def load_all_bullets(session, store) -> list[tuple[int, str, list[np.ndarray]]]:
    """Every bullet (known + questioned) as ``(barrel_no, key, signatures)``."""
    import verity_catalog.models as m
    from sqlmodel import select

    out = []
    for firearm in session.exec(select(m.Firearm)).all():
        if not (firearm.external_id or "").startswith("Barrel"):
            continue
        barrel_no = int(firearm.external_id.removeprefix("Barrel"))
        for bullet in session.exec(select(m.Bullet).where(m.Bullet.firearm_id == firearm.id)).all():
            lands = session.exec(
                select(m.Land).where(m.Land.bullet_id == bullet.id).order_by(m.Land.position)
            ).all()
            sigs = []
            for land in lands:
                scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
                if scan is not None:
                    surface = read_surface(store.get(scan.content_hash))
                    sigs.append(
                        striation_signature(
                            surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C, orient=ORIENT
                        )
                    )
            if sigs:
                out.append((barrel_no, bullet.external_id, sigs))
    return out


def pairwise_scores(bullets):
    """Bullet-to-bullet scores with KM/KNM labels and the barrel of each side."""
    scores, labels, barrels_a, barrels_b = [], [], [], []
    for (ba, _ka, sa), (bb, _kb, sb) in combinations(bullets, 2):
        s = bullet_score(sa, sb)
        if not np.isfinite(s):
            continue
        scores.append(s)
        labels.append(1 if ba == bb else 0)
        barrels_a.append(ba)
        barrels_b.append(bb)
    return (np.array(scores), np.array(labels), np.array(barrels_a), np.array(barrels_b))


def barrel_disjoint_folds(scores, labels, ba, bb, *, n_splits=10, test_frac=0.4, seed=0):
    """Calibrate on train barrels, score held-out test barrels; no barrel spans
    both. Pairs straddling the split are dropped."""
    barrels = sorted(set(ba.tolist()) | set(bb.tolist()))
    rng = np.random.default_rng(seed)
    n_test = max(2, round(len(barrels) * test_frac))
    rows = []
    for _ in range(n_splits):
        test_b = set(rng.permutation(barrels)[:n_test].tolist())
        in_test = np.array([x in test_b and y in test_b for x, y in zip(ba, bb, strict=True)])
        in_train = np.array(
            [x not in test_b and y not in test_b for x, y in zip(ba, bb, strict=True)]
        )
        if labels[in_train].sum() < 3 or labels[in_test].sum() < 1:
            continue
        model = ScoreLRModel().fit(scores[in_train], labels[in_train])
        lr = model.predict_lr(scores[in_test])
        rows.append(
            {
                "cllr": cllr(lr[labels[in_test] == 1], lr[labels[in_test] == 0]),
                "cllr_min": cllr_min(scores[in_test], labels[in_test]),
                "auc": roc_auc(scores[in_test], labels[in_test]),
            }
        )
    return rows


def evaluate() -> dict:
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    with Session(engine) as session:
        bullets = load_all_bullets(session, store)
    scores, labels, ba, bb = pairwise_scores(bullets)
    folds = barrel_disjoint_folds(scores, labels, ba, bb) if len(scores) else []
    return {"n_bullets": len(bullets), "scores": scores, "labels": labels, "folds": folds}


def main() -> None:
    res = evaluate()
    if res["n_bullets"] == 0:
        print("No Hamby data — ingest the 'hamby-252' manifest first.")
        return
    scores, labels, folds = res["scores"], res["labels"], res["folds"]
    print(
        f"bullets={res['n_bullets']}  pairs={len(scores)}  "
        f"(KM={int(labels.sum())}, KNM={int((labels == 0).sum())})"
    )
    print(
        f"overall AUC={roc_auc(scores, labels):.3f}  pooled Cllr_min={cllr_min(scores, labels):.3f}"
    )
    if folds:
        c = np.array([f["cllr"] for f in folds])
        cm = np.array([f["cllr_min"] for f in folds])
        au = np.array([f["auc"] for f in folds])
        print(f"barrel-disjoint over {len(folds)} splits:")
        print(f"  test Cllr     = {c.mean():.3f} +/- {c.std():.3f}")
        print(f"  test Cllr_min = {cm.mean():.3f} +/- {cm.std():.3f}")
        print(f"  test AUC      = {au.mean():.3f} +/- {au.std():.3f}")
        print(f"  calibration loss (Cllr - Cllr_min) = {c.mean() - cm.mean():+.3f}")


if __name__ == "__main__":
    main()
