"""Phase-2b experiment: does a learned representation beat the hand-engineered
cross-correlation, **barrel-disjoint**, on each bullet dataset?

Bootstraps same-source land-pair labels from the Phase-1 diagonal, trains the
encoder on TRAIN barrels only, and compares the learned-cosine ``Cllr`` to the
CCF ``Cllr`` on HELD-OUT barrels (an identical, paired split for both). Reported
per study (never pooling makes), and honest about the data limit.

Run after ingesting one or more bullet studies and installing the ``learn`` +
``demo`` extras: ``uv run verity-learn-hamby``
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from verity import ScoreLRModel, align_1d, cllr, roc_auc
from verity.examples.hamby_km_knm import _catalog_dir
from verity.examples.hamby_validation import (
    _resolve_study,
    iter_bullet_studies,
    load_study_bullets,
)
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


def _evaluate_bullets(bullets, *, n_splits: int, test_frac: float, seed: int) -> dict:
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


def _open_catalog():
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    return Session(engine), store


def evaluate(
    *,
    n_splits: int = 5,
    test_frac: float = 0.4,
    seed: int = 0,
    study_external_id: str | None = None,
) -> dict:
    """Learned-vs-CCF on one study (defaults to the Hamby-252 anchor)."""
    session, store = _open_catalog()
    with session:
        study = _resolve_study(session, study_external_id)
        bullets = load_study_bullets(session, store, study) if study is not None else []
        title = (study.title or study.external_id) if study is not None else ""
    res = _evaluate_bullets(bullets, n_splits=n_splits, test_frac=test_frac, seed=seed)
    res["title"] = title
    return res


def evaluate_all(*, n_splits: int = 5, test_frac: float = 0.4, seed: int = 0) -> list[dict]:
    """Learned-vs-CCF for every bullet study, each trained/tested on its own barrels."""
    session, store = _open_catalog()
    with session:
        studies = iter_bullet_studies(session)
        loaded = [
            (s.title or s.external_id, load_study_bullets(session, store, s)) for s in studies
        ]
    results = []
    for title, bullets in loaded:
        if not bullets:
            continue
        res = _evaluate_bullets(bullets, n_splits=n_splits, test_frac=test_frac, seed=seed)
        res["title"] = title
        results.append(res)
    return results


def evaluate_pooled(*, n_splits: int = 5, test_frac: float = 0.4, seed: int = 0) -> list[dict]:
    """Train ONE encoder per split on pooled train-barrels across ALL studies,
    then evaluate per study on its own held-out test barrels.

    This is the test the dataset expansion exists for: does more data — and the
    cross-make diversity of negatives — close the learned-vs-CCF gap that the
    single-study, data-limited experiment leaves open? Barrel-disjointness is
    preserved per study (a study's test barrels are in neither the pooled encoder
    training set nor that study's calibration set)."""
    session, store = _open_catalog()
    with session:
        studies = iter_bullet_studies(session)
        per_study = [
            (s.title or s.external_id, load_study_bullets(session, store, s)) for s in studies
        ]
    per_study = [(t, b) for t, b in per_study if b]
    if not per_study:
        return []

    ccf_cache = {t: ccf_pairs(bs) for t, bs in per_study}  # split-independent
    rng = np.random.default_rng(seed)
    folds_by_study: dict[str, list] = {t: [] for t, _ in per_study}

    for split in range(n_splits):
        pooled_train, test_by_study = [], {}
        for t, bs in per_study:
            barrels = sorted({b[0] for b in bs})
            n_test = max(2, round(len(barrels) * test_frac))
            test_b = set(rng.permutation(barrels)[:n_test].tolist())
            test_by_study[t] = test_b
            pooled_train += [b for b in bs if b[0] not in test_b]
        a, b_pos, y = bootstrap_pairs(pooled_train, seed=seed + split)
        encoder = train_encoder(a, b_pos, y, seed=seed + split)
        for t, bs in per_study:
            ls, ll, lba, lbb = learned_pairs(bs, encoder)
            cs, cl, ba, bb = ccf_cache[t]
            ccf = _fold_metrics(cs, cl, ba, bb, test_by_study[t])
            learned = _fold_metrics(ls, ll, lba, lbb, test_by_study[t])
            if ccf and learned:
                folds_by_study[t].append({"ccf": ccf, "learned": learned})

    return [{"title": t, "n_bullets": len(bs), "folds": folds_by_study[t]} for t, bs in per_study]


def _print_study(res: dict) -> None:
    folds = res["folds"]
    print(f"=== {res['title']}  (bullets={res['n_bullets']}, folds={len(folds)}) ===")
    if not folds:
        print("  (too few barrels for a disjoint split)")
        return
    ccf_cllr = np.array([f["ccf"]["cllr"] for f in folds])
    learned_cllr = np.array([f["learned"]["cllr"] for f in folds])
    ccf_auc = np.array([f["ccf"]["auc"] for f in folds])
    learned_auc = np.array([f["learned"]["auc"] for f in folds])
    print(
        f"  CCF     : Cllr={ccf_cllr.mean():.3f} +/- {ccf_cllr.std():.3f}  "
        f"AUC={ccf_auc.mean():.3f}"
    )
    print(
        f"  learned : Cllr={learned_cllr.mean():.3f} +/- {learned_cllr.std():.3f}  "
        f"AUC={learned_auc.mean():.3f}"
    )
    delta = float(ccf_cllr.mean() - learned_cllr.mean())
    verdict = "beats" if delta > 0 else "does NOT beat"
    print(f"  -> learned {verdict} CCF by {delta:+.3f} Cllr (positive = learned better)")


def main() -> None:
    results = evaluate_all()
    if not results:
        print("No bullet data — ingest a bullet manifest (e.g. 'hamby-252') first.")
        return
    print("Encoder trained PER STUDY (each study's own train barrels):\n")
    for res in results:
        _print_study(res)


def pooled_main() -> None:
    results = evaluate_pooled()
    if not results:
        print("No bullet data — ingest a bullet manifest (e.g. 'hamby-252') first.")
        return
    print("Encoder trained on POOLED train-barrels (all studies); evaluated per study:\n")
    for res in results:
        _print_study(res)


if __name__ == "__main__":
    main()
