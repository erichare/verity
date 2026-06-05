"""Phase-2b experiment: does a learned representation beat the hand-engineered
cross-correlation, **barrel-disjoint**, on Hamby 252?

Bootstraps same-source land-pair labels from the Phase-1 diagonal, trains the
encoder on TRAIN barrels only, and compares the learned-cosine ``Cllr`` to the
CCF ``Cllr`` on HELD-OUT barrels (an identical, paired split for both). Honest
about the data limit (210 scans).

Run after ingesting hamby-252 and installing the ``learn`` + ``demo`` extras:
``uv run verity-learn-hamby``
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import ScoreLRModel, align_1d, cllr, roc_auc
from verity.examples.hamby_km_knm import _catalog_dir
from verity.examples.hamby_validation import load_all_bullets
from verity.representation import bootstrap_pairs, embed, train_encoder


def diagonal_score(sim: np.ndarray) -> float:
    """Best mean land-to-land similarity over cyclic land rotations."""
    n, m = sim.shape
    return float(max(np.mean([sim[i, (i + k) % m] for i in range(n)]) for k in range(m)))


def _pairs(bullets, sim_matrix):
    """Bullet-pair scores + labels + barrels, using ``sim_matrix(rep_a, rep_b)``."""
    scores, labels, ba, bb = [], [], [], []
    for (a_barrel, _ak, a_rep), (b_barrel, _bk, b_rep) in combinations(bullets, 2):
        scores.append(diagonal_score(sim_matrix(a_rep, b_rep)))
        labels.append(1 if a_barrel == b_barrel else 0)
        ba.append(a_barrel)
        bb.append(b_barrel)
    return np.array(scores), np.array(labels), np.array(ba), np.array(bb)


def ccf_pairs(bullets):
    return _pairs(bullets, lambda sa, sb: np.array([[align_1d(a, b)[1] for b in sb] for a in sa]))


def learned_pairs(bullets, encoder):
    embedded = [(barrel, key, embed(encoder, sigs)) for barrel, key, sigs in bullets]
    return _pairs(embedded, lambda ea, eb: ea @ eb.T)  # cosine (rows are L2-normalized)


def _fold_metrics(scores, labels, ba, bb, test_barrels):
    in_test = np.array(
        [x in test_barrels and y in test_barrels for x, y in zip(ba, bb, strict=True)]
    )
    in_train = np.array(
        [x not in test_barrels and y not in test_barrels for x, y in zip(ba, bb, strict=True)]
    )
    if labels[in_train].sum() < 3 or labels[in_test].sum() < 1:
        return None
    model = ScoreLRModel().fit(scores[in_train], labels[in_train])
    lr = model.predict_lr(scores[in_test])
    return {
        "cllr": cllr(lr[labels[in_test] == 1], lr[labels[in_test] == 0]),
        "auc": roc_auc(scores[in_test], labels[in_test]),
    }


def evaluate(*, n_splits: int = 5, test_frac: float = 0.4, seed: int = 0) -> dict:
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    with Session(engine) as session:
        bullets = load_all_bullets(session, store)
    if not bullets:
        return {"n_bullets": 0, "folds": []}

    # CCF scores don't depend on the split — compute once.
    ccf_scores, ccf_labels, ba, bb = ccf_pairs(bullets)
    barrels = sorted(set(ba.tolist()) | set(bb.tolist()))
    n_test = max(2, round(len(barrels) * test_frac))
    rng = np.random.default_rng(seed)

    folds = []
    for split in range(n_splits):
        test_barrels = set(rng.permutation(barrels)[:n_test].tolist())
        train_bullets = [b for b in bullets if b[0] not in test_barrels]
        a, b_pos, y = bootstrap_pairs(train_bullets, seed=seed + split)
        encoder = train_encoder(a, b_pos, y, seed=seed + split)
        learned_scores, learned_labels, lba, lbb = learned_pairs(bullets, encoder)

        ccf = _fold_metrics(ccf_scores, ccf_labels, ba, bb, test_barrels)
        learned = _fold_metrics(learned_scores, learned_labels, lba, lbb, test_barrels)
        if ccf and learned:
            folds.append({"ccf": ccf, "learned": learned})
    return {"n_bullets": len(bullets), "folds": folds}


def main() -> None:
    res = evaluate()
    if res["n_bullets"] == 0:
        print("No Hamby data — ingest the 'hamby-252' manifest first.")
        return
    folds = res["folds"]
    ccf_cllr = np.array([f["ccf"]["cllr"] for f in folds])
    learned_cllr = np.array([f["learned"]["cllr"] for f in folds])
    ccf_auc = np.array([f["ccf"]["auc"] for f in folds])
    learned_auc = np.array([f["learned"]["auc"] for f in folds])
    print(f"bullets={res['n_bullets']}  barrel-disjoint folds={len(folds)}")
    print(
        f"  CCF     : Cllr={ccf_cllr.mean():.3f} +/- {ccf_cllr.std():.3f}  AUC={ccf_auc.mean():.3f}"
    )
    print(
        f"  learned : Cllr={learned_cllr.mean():.3f} +/- {learned_cllr.std():.3f}  "
        f"AUC={learned_auc.mean():.3f}"
    )
    delta = float(ccf_cllr.mean() - learned_cllr.mean())
    verdict = "beats" if delta > 0 else "does NOT beat"
    print(f"  -> learned {verdict} CCF by {delta:+.3f} Cllr (positive = learned better)")


if __name__ == "__main__":
    main()
