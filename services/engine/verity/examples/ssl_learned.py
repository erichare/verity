"""Stage-A SSL evaluation: does masked-autoencoder pretraining on ALL unlabeled
surfaces let the learned representation close the gap to CCF that the from-scratch
2-D encoder could not?

Pretrain the conv encoder once on every land image, pooled across studies and
unlabeled (transductive — inputs only, no label leak). Then, per study and per
barrel-disjoint fold, fine-tune a thin metric head from the pretrained encoder on
the TRAIN barrels and score the held-out ones, against the CCF baseline (and, for
reference, the from-scratch surface encoder from Phase 2).

Run with the ``learn`` + ``demo`` extras: ``uv run verity-learn-ssl``
"""

from __future__ import annotations

import copy
import os
from itertools import combinations

import numpy as np

from verity.examples.hamby_km_knm import _catalog_dir
from verity.examples.hamby_learned import _fold_metrics, diagonal_score
from verity.examples.hamby_validation import iter_bullet_studies
from verity.examples.surface_learned import SIZE, bootstrap_land_pairs, ccf_pairs, load_study
from verity.representation import MAEEmbedder, embed_mae, finetune_mae, pretrain_mae

# Strong, meaningfully-baselined datasets (tall scans) — the fair test for SSL.
STRONG_EXT = {"c09aaa86-5d60-4acb-9031-46dad2c0ad32", "fcafffb1-b96c-49c7-9a9f-b1ec9849f884"}


def learned_pairs(bullets, embedder):
    emb = [(bar, embed_mae(embedder, imgs)) for bar, _k, _s, imgs in bullets]
    scores, labels, ba, bb = [], [], [], []
    for (a_bar, ea), (b_bar, eb) in combinations(emb, 2):
        scores.append(diagonal_score(ea @ eb.T))
        labels.append(1 if a_bar == b_bar else 0)
        ba.append(a_bar)
        bb.append(b_bar)
    return np.array(scores), np.array(labels), np.array(ba), np.array(bb)


def evaluate_study(
    bullets, pretrained, *, n_splits: int = 3, test_frac: float = 0.4, seed: int = 0
):
    ccf_scores, ccf_labels, ba, bb = ccf_pairs(bullets)
    barrels = sorted(set(ba.tolist()) | set(bb.tolist()))
    n_test = max(2, round(len(barrels) * test_frac))
    rng = np.random.default_rng(seed)

    folds = []
    for split in range(n_splits):
        test_barrels = set(rng.permutation(barrels)[:n_test].tolist())
        train_bullets = [b for b in bullets if b[0] not in test_barrels]
        a, b_pos, yy = bootstrap_land_pairs(train_bullets, seed=seed + split)
        freeze = os.environ.get("VERITY_SSL_FREEZE", "0") not in ("0", "false", "False")
        embedder = MAEEmbedder(copy.deepcopy(pretrained))
        finetune_mae(embedder, a, b_pos, yy, freeze_encoder=freeze, seed=seed + split)
        ls, ll, lba, lbb = learned_pairs(bullets, embedder)
        ccf = _fold_metrics(ccf_scores, ccf_labels, ba, bb, test_barrels)
        ssl = _fold_metrics(ls, ll, lba, lbb, test_barrels)
        if ccf and ssl:
            folds.append({"ccf": ccf, "ssl": ssl})
    return {"n_bullets": len(bullets), "folds": folds}


def evaluate(*, n_splits: int = 3, seed: int = 0) -> list[dict]:
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    cache_dir = cdir / ".verity" / "cache" / f"land{SIZE}"
    cache_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")

    with Session(engine) as session:
        studies = iter_bullet_studies(session)
        loaded = [
            (s.title or s.external_id, s.external_id, load_study(session, store, s, cache_dir))
            for s in studies
        ]

    # Stage A: pretrain on EVERY land image, pooled and unlabeled.
    all_imgs = [img for _, _, bullets in loaded for _, _, _, imgs in bullets for img in imgs]
    print(f"pretraining MAE on {len(all_imgs)} unlabeled land images ...")
    pretrained = pretrain_mae(all_imgs, seed=seed)

    results = []
    for title, ext, bullets in loaded:
        if ext not in STRONG_EXT or not bullets:
            continue
        res = evaluate_study(bullets, pretrained, n_splits=n_splits, seed=seed)
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
    sc = np.array([f["ssl"]["cllr"] for f in folds])
    ca = np.array([f["ccf"]["auc"] for f in folds])
    sa = np.array([f["ssl"]["auc"] for f in folds])
    print(f"  CCF        : Cllr={cc.mean():.3f}  AUC={ca.mean():.3f}")
    print(f"  SSL+head   : Cllr={sc.mean():.3f} +/- {sc.std():.3f}  AUC={sa.mean():.3f}")
    print(f"  -> SSL {'beats' if cc.mean() - sc.mean() > 0 else 'does NOT beat'} CCF "
          f"by {cc.mean() - sc.mean():+.3f} Cllr")


def main() -> None:
    results = evaluate()
    if not results:
        print("No bullet data — ingest a bullet manifest first.")
        return
    print("\nMAE-pretrained encoder + fine-tuned head vs CCF, barrel-disjoint:\n")
    for res in results:
        _print_study(res)


if __name__ == "__main__":
    main()
