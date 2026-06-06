"""Phase 2: the 2-D **surface** encoder vs the CCF baseline, barrel-disjoint per
study.

Phase 2b embedded the collapsed 1-D signature and lost to CCF; here the encoder
sees the full 2-D orientation-normalized land image (``land_image``). Same
harness as ``hamby_learned`` — bootstrap same-source land pairs from the Phase-1
diagonal, train on TRAIN barrels only, compare learned-cosine ``Cllr`` to CCF on
HELD-OUT barrels — but per study, so negatives are within-make (no cross-make
shortcut). Land features are cached by content hash, so re-runs are fast.

Run after ingesting bullet studies + the ``learn``/``demo`` extras:
``uv run verity-learn-surface``
"""

from __future__ import annotations

import os
from itertools import combinations

import numpy as np

from verity import align_1d
from verity.examples.hamby_km_knm import (
    LAMBDA_C,
    LAMBDA_S,
    ORIENT,
    _catalog_dir,
    read_surface,
)
from verity.examples.hamby_learned import _fold_metrics, diagonal_score
from verity.examples.hamby_validation import iter_bullet_studies
from verity.representation import embed_surfaces, land_image, train_surface_encoder
from verity.representation.labels import best_rotation
from verity.signature import striation_signature

SIZE = int(os.environ.get("VERITY_LAND_SIZE", "64"))


def _features(surface) -> tuple[np.ndarray, np.ndarray]:
    """(1-D signature for CCF + correspondence, 2-D land image for the encoder)."""
    sig = striation_signature(surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C, orient=ORIENT)
    img = land_image(surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C, size=SIZE, orient=ORIENT)
    return sig, img


def _cached_features(store, content_hash, cache_dir):
    path = cache_dir / f"{content_hash}.npz"
    if path.exists():
        d = np.load(path)
        return d["sig"], d["img"]
    sig, img = _features(read_surface(store.get(content_hash)))
    np.savez(path, sig=sig, img=img)
    return sig, img


def load_study(session, store, study, cache_dir):
    """``[(barrel_key, bullet_key, signatures, land_images)]`` for one study."""
    import verity_catalog.models as m
    from sqlmodel import select

    out = []
    for firearm in session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all():
        for bullet in session.exec(select(m.Bullet).where(m.Bullet.firearm_id == firearm.id)).all():
            lands = session.exec(
                select(m.Land).where(m.Land.bullet_id == bullet.id).order_by(m.Land.position)
            ).all()
            sigs, imgs = [], []
            for land in lands:
                scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
                if scan is None:
                    continue
                sig, img = _cached_features(store, scan.content_hash, cache_dir)
                sigs.append(sig)
                imgs.append(img)
            if sigs:
                out.append((firearm.id, bullet.external_id, sigs, imgs))
    return out


def ccf_pairs(bullets):
    scores, labels, ba, bb = [], [], [], []
    for (a_bar, _ak, sa, _ia), (b_bar, _bk, sb, _ib) in combinations(bullets, 2):
        sim = np.array([[align_1d(x, y)[1] for y in sb] for x in sa])
        scores.append(diagonal_score(sim))
        labels.append(1 if a_bar == b_bar else 0)
        ba.append(a_bar)
        bb.append(b_bar)
    return np.array(scores), np.array(labels), np.array(ba), np.array(bb)


def learned_pairs(bullets, encoder):
    emb = [(bar, embed_surfaces(encoder, imgs)) for bar, _k, _s, imgs in bullets]
    scores, labels, ba, bb = [], [], [], []
    for (a_bar, ea), (b_bar, eb) in combinations(emb, 2):
        scores.append(diagonal_score(ea @ eb.T))
        labels.append(1 if a_bar == b_bar else 0)
        ba.append(a_bar)
        bb.append(b_bar)
    return np.array(scores), np.array(labels), np.array(ba), np.array(bb)


def bootstrap_land_pairs(bullets, *, neg_ratio: int = 4, seed: int = 0):
    """Same-source land-image positives (aligned by the 1-D diagonal) + sampled
    different-source negatives. ``bullets`` are from ONE study, so negatives are
    within-make."""
    rng = np.random.default_rng(seed)
    a_imgs, b_imgs, y, negatives = [], [], [], []
    for (a_bar, _ak, sa, ia), (b_bar, _bk, sb, ib) in combinations(bullets, 2):
        if a_bar == b_bar:
            offset = best_rotation(sa, sb)
            m = len(ib)
            for i in range(len(ia)):
                a_imgs.append(ia[i])
                b_imgs.append(ib[(i + offset) % m])
                y.append(1)
        else:
            for i in range(min(len(ia), len(ib))):
                negatives.append((ia[i], ib[i]))
    n_neg = neg_ratio * sum(y)
    if len(negatives) > n_neg:
        negatives = [negatives[i] for i in rng.choice(len(negatives), n_neg, replace=False)]
    for a, b in negatives:
        a_imgs.append(a)
        b_imgs.append(b)
        y.append(0)
    return a_imgs, b_imgs, np.array(y)


def evaluate_study(bullets, *, n_splits: int = 3, test_frac: float = 0.4, seed: int = 0) -> dict:
    ccf_scores, ccf_labels, ba, bb = ccf_pairs(bullets)
    barrels = sorted(set(ba.tolist()) | set(bb.tolist()))
    n_test = max(2, round(len(barrels) * test_frac))
    rng = np.random.default_rng(seed)

    folds = []
    for split in range(n_splits):
        test_barrels = set(rng.permutation(barrels)[:n_test].tolist())
        train_bullets = [b for b in bullets if b[0] not in test_barrels]
        a, b_pos, yy = bootstrap_land_pairs(train_bullets, seed=seed + split)
        encoder = train_surface_encoder(a, b_pos, yy, seed=seed + split)
        ls, ll, lba, lbb = learned_pairs(bullets, encoder)
        ccf = _fold_metrics(ccf_scores, ccf_labels, ba, bb, test_barrels)
        learned = _fold_metrics(ls, ll, lba, lbb, test_barrels)
        if ccf and learned:
            folds.append({"ccf": ccf, "learned": learned})
    return {"n_bullets": len(bullets), "folds": folds}


def evaluate_all(*, n_splits: int = 3, seed: int = 0) -> list[dict]:
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    cache_dir = cdir / ".verity" / "cache" / f"land{SIZE}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")

    only = {x for x in os.environ.get("VERITY_STUDIES", "").split(",") if x}
    results = []
    with Session(engine) as session:
        studies = [s for s in iter_bullet_studies(session) if not only or s.external_id in only]
        loaded = [
            (s.title or s.external_id, load_study(session, store, s, cache_dir)) for s in studies
        ]
    for title, bullets in loaded:
        if not bullets:
            continue
        res = evaluate_study(bullets, n_splits=n_splits, seed=seed)
        res["title"] = title
        results.append(res)
    return results


def _print_study(res: dict) -> None:
    folds = res["folds"]
    print(f"=== {res['title']}  (bullets={res['n_bullets']}, folds={len(folds)}) ===")
    if not folds:
        print("  (too few barrels for a disjoint split)")
        return
    cc = np.array([f["ccf"]["cllr"] for f in folds])
    lc = np.array([f["learned"]["cllr"] for f in folds])
    ca = np.array([f["ccf"]["auc"] for f in folds])
    la = np.array([f["learned"]["auc"] for f in folds])
    print(f"  CCF      : Cllr={cc.mean():.3f} +/- {cc.std():.3f}  AUC={ca.mean():.3f}")
    print(f"  surface  : Cllr={lc.mean():.3f} +/- {lc.std():.3f}  AUC={la.mean():.3f}")
    delta = float(cc.mean() - lc.mean())
    print(f"  -> surface {'beats' if delta > 0 else 'does NOT beat'} CCF by {delta:+.3f} Cllr")


def main() -> None:
    results = evaluate_all()
    if not results:
        print("No bullet data — ingest a bullet manifest first.")
        return
    print(f"2-D surface encoder vs CCF, barrel-disjoint per study (land {SIZE}x{SIZE}):\n")
    for res in results:
        _print_study(res)


if __name__ == "__main__":
    main()
