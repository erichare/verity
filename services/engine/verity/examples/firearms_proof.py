"""Phase 3 — the firearms proof: Verity's first-principles CCF + calibrated LR
vs the **bulletxtrctr** random forest (the hand-tuned specialist), barrel
disjoint, per dataset.

Both systems score the *same* bullet pairs and are split the *same* way (no
barrel in train + test); each fits its own score→LR calibration on the train
barrels and is scored on the held-out ones. The claim is not that Verity
discriminates better — it is that a transparent, first-principles pipeline
matches the specialist's ``Cllr`` with comparable ``Cllr_min`` and **smaller
calibration loss**, the answer to the Cuellar et al. (2024) critique.

bulletxtrctr (R) is a baseline COMPETITOR only — never in Verity's runtime path.
Run after ingesting bullet studies, with R + bulletxtrctr installed:
``uv run verity-firearms-proof``
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import roc_auc
from verity.examples.hamby_km_knm import (
    LAMBDA_C,
    LAMBDA_S,
    ORIENT,
    _catalog_dir,
    bullet_score,
    read_surface,
)
from verity.examples.hamby_validation import barrel_disjoint_folds
from verity.signature import striation_signature

# The strong, meaningfully-baselined bullet datasets (tall scans).
STUDIES = [
    ("Hamby-252", "c09aaa86-5d60-4acb-9031-46dad2c0ad32"),
    ("PGPD Beretta", "fcafffb1-b96c-49c7-9a9f-b1ec9849f884"),
]


def load_bullets(session, store, study):
    """``(firearm_id, bullet_id, signatures)`` per bullet of a study."""
    import verity_catalog.models as m
    from sqlmodel import select

    out = []
    for firearm in session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all():
        for bullet in session.exec(select(m.Bullet).where(m.Bullet.firearm_id == firearm.id)).all():
            sigs = []
            for land in session.exec(
                select(m.Land).where(m.Land.bullet_id == bullet.id).order_by(m.Land.position)
            ).all():
                scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
                if scan is not None:
                    sigs.append(
                        striation_signature(
                            read_surface(store.get(scan.content_hash)),
                            lambda_s=LAMBDA_S,
                            lambda_c=LAMBDA_C,
                            orient=ORIENT,
                        )
                    )
            if sigs:
                out.append((firearm.id, bullet.id, sigs))
    return out


def verity_pairs(bullets) -> dict:
    """``frozenset{bullet_id_a, bullet_id_b}`` → ``(ccf_score, label, barrel_a, barrel_b)``."""
    out = {}
    for (fa, ida, sa), (fb, idb, sb) in combinations(bullets, 2):
        out[frozenset((ida, idb))] = (bullet_score(sa, sb), 1 if fa == fb else 0, fa, fb)
    return out


def evaluate_study(session, store, study, work_dir):
    from verity.baselines.bulletxtrctr import bulletxtrctr_scores

    bullets = load_bullets(session, store, study)
    vpairs = verity_pairs(bullets)
    bx = bulletxtrctr_scores(session, store, study, work_dir)
    bxmap = {frozenset((r["bullet_a"], r["bullet_b"])): r["score"] for r in bx}

    v, b, y, ba, bb = [], [], [], [], []
    for key, (vscore, label, barrel_a, barrel_b) in vpairs.items():
        bscore = bxmap.get(key, float("nan"))
        if np.isfinite(vscore) and np.isfinite(bscore):
            v.append(vscore)
            b.append(bscore)
            y.append(label)
            ba.append(barrel_a)
            bb.append(barrel_b)
    v, b, y, ba, bb = (np.array(x) for x in (v, b, y, ba, bb))
    return {
        "n_pairs": len(y),
        "n_km": int(y.sum()),
        "verity_auc": roc_auc(v, y) if len(y) else float("nan"),
        "bx_auc": roc_auc(b, y) if len(y) else float("nan"),
        "verity_folds": barrel_disjoint_folds(v, y, ba, bb) if len(y) else [],
        "bx_folds": barrel_disjoint_folds(b, y, ba, bb) if len(y) else [],
    }


def _fold_stats(folds, key):
    return np.array([f[key] for f in folds]) if folds else np.array([np.nan])


def _print_study(name, res):
    vf, bf = res["verity_folds"], res["bx_folds"]
    print(f"=== {name}  (pairs={res['n_pairs']}, KM={res['n_km']}, folds={len(vf)}) ===")
    print(f"  overall AUC      : Verity {res['verity_auc']:.3f}   bulletxtrctr {res['bx_auc']:.3f}")
    for label, folds in (("Verity (CCF+LR)", vf), ("bulletxtrctr (RF)", bf)):
        c, cm, au = (_fold_stats(folds, k) for k in ("cllr", "cllr_min", "auc"))
        print(
            f"  {label:18s}: Cllr={c.mean():.3f}+/-{c.std():.3f}  "
            f"Cllr_min={cm.mean():.3f}  AUC={au.mean():.3f}  "
            f"calib-loss={c.mean() - cm.mean():+.3f}"
        )
    dv = _fold_stats(vf, "cllr").mean()
    db = _fold_stats(bf, "cllr").mean()
    verdict = "matches/beats" if dv <= db + 0.05 else "trails"
    print(f"  -> Verity {verdict} bulletxtrctr on Cllr ({dv:.3f} vs {db:.3f})")


def main() -> None:
    import verity_catalog.models as m
    from sqlmodel import Session, create_engine, select
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    print("Phase 3 — Verity CCF+LR vs bulletxtrctr RF, barrel-disjoint:")
    print(
        "  NOTE: bulletxtrctr's random forest was trained on Hamby data, so its\n"
        "  Hamby score is ~in-sample; the fair comparison is out-of-domain (Beretta),\n"
        "  where its calibration loss can exceed Verity's untrained, stable one.\n"
    )
    with Session(engine) as session:
        for name, ext in STUDIES:
            study = session.exec(select(m.Study).where(m.Study.external_id == ext)).first()
            if study is None:
                continue
            work_dir = cdir / ".verity" / "cache" / "bulletxtrctr" / ext
            res = evaluate_study(session, store, study, work_dir)
            _print_study(name, res)


if __name__ == "__main__":
    main()
