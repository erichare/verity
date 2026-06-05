"""Phase-2 validation: turn the Phase-1 bullet-comparison scores into calibrated
likelihood ratios and characterize them with a **barrel-disjoint** ``Cllr``,
reported **per dataset** (never pooled across makes).

Splitting by barrel (no barrel in both train and test) is the source-disjoint
discipline whose absence the Cuellar et al. (2024) critique flags. The result is
a weight of evidence with a characterized cost *on a named dataset* — not a
field-wide error-rate claim. Each study is reported on its own: pooling distinct
makes would seed the KNM set with trivially-easy cross-make pairs and inflate the
numbers, the opposite of honest reporting.

The barrel identity is the globally-unique ``Firearm.id`` (one row per physical
barrel per study), so two studies that both label barrels ``Barrel1..10`` never
collide.

Run after ingesting one or more bullet studies:  ``uv run verity-validate``
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

# The original Phase-2a anchor dataset — the default for ``evaluate()`` so the
# data-gated regression test keeps its Hamby-252 meaning.
HAMBY_252_EXTERNAL_ID = "c09aaa86-5d60-4acb-9031-46dad2c0ad32"


def load_study_bullets(session, store, study) -> list[tuple[int, str, list[np.ndarray]]]:
    """Every bullet of one study as ``(barrel_key, bullet_key, signatures)``.

    ``barrel_key`` is the globally-unique ``Firearm.id`` (the physical barrel),
    so KM = same firearm and barrel keys never collide across studies."""
    import verity_catalog.models as m
    from sqlmodel import select

    out: list[tuple[int, str, list[np.ndarray]]] = []
    firearms = session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all()
    for firearm in firearms:
        for bullet in session.exec(
            select(m.Bullet).where(m.Bullet.firearm_id == firearm.id)
        ).all():
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
                out.append((firearm.id, bullet.external_id, sigs))
    return out


def load_all_bullets(session, store, study=None) -> list[tuple[int, str, list[np.ndarray]]]:
    """Bullets keyed by globally-unique ``Firearm.id``. Scoped to one ``study``
    (a ``Study`` row), or every study when ``study is None``."""
    import verity_catalog.models as m
    from sqlmodel import select

    studies = [study] if study is not None else session.exec(select(m.Study)).all()
    out: list[tuple[int, str, list[np.ndarray]]] = []
    for st in studies:
        out.extend(load_study_bullets(session, store, st))
    return out


def iter_bullet_studies(session) -> list:
    """Studies that have at least one firearm (bullet datasets), in id order."""
    import verity_catalog.models as m
    from sqlmodel import select

    studies = session.exec(select(m.Study)).all()
    out = []
    for study in studies:
        has_firearm = session.exec(
            select(m.Firearm).where(m.Firearm.study_id == study.id)
        ).first()
        if has_firearm is not None:
            out.append(study)
    return out


def _resolve_study(session, external_id: str | None):
    """The named study, else the Hamby-252 anchor, else the first bullet study."""
    import verity_catalog.models as m
    from sqlmodel import select

    target = external_id or HAMBY_252_EXTERNAL_ID
    study = session.exec(select(m.Study).where(m.Study.external_id == target)).first()
    if study is not None:
        return study
    studies = iter_bullet_studies(session)
    return studies[0] if studies else None


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


def evaluate(study_external_id: str | None = None) -> dict:
    """Single-study barrel-disjoint evaluation (defaults to the Hamby-252 anchor)."""
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    with Session(engine) as session:
        study = _resolve_study(session, study_external_id)
        if study is None:
            return {"n_bullets": 0, "scores": np.array([]), "labels": np.array([]), "folds": []}
        bullets = load_study_bullets(session, store, study)
        title = study.title or study.external_id
    scores, labels, ba, bb = pairwise_scores(bullets)
    folds = barrel_disjoint_folds(scores, labels, ba, bb) if len(scores) else []
    n_barrels = len(set(ba.tolist()) | set(bb.tolist())) if len(scores) else 0
    return {
        "title": title,
        "n_bullets": len(bullets),
        "n_barrels": n_barrels,
        "scores": scores,
        "labels": labels,
        "folds": folds,
    }


def evaluate_all() -> list[dict]:
    """One barrel-disjoint result per bullet study in the catalog."""
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    results = []
    with Session(engine) as session:
        studies = iter_bullet_studies(session)
        for study in studies:
            bullets = load_study_bullets(session, store, study)
            if not bullets:
                continue
            scores, labels, ba, bb = pairwise_scores(bullets)
            if not len(scores):
                continue
            results.append(
                {
                    "title": study.title or study.external_id,
                    "n_bullets": len(bullets),
                    "n_barrels": len(set(ba.tolist()) | set(bb.tolist())),
                    "scores": scores,
                    "labels": labels,
                    "folds": barrel_disjoint_folds(scores, labels, ba, bb),
                }
            )
    return results


def _print_study(res: dict) -> None:
    scores, labels, folds = res["scores"], res["labels"], res["folds"]
    print(
        f"=== {res['title']}  "
        f"({res['n_barrels']} barrels, {res['n_bullets']} bullets) ==="
    )
    print(
        f"  pairs={len(scores)}  KM={int(labels.sum())}  KNM={int((labels == 0).sum())}  "
        f"AUC={roc_auc(scores, labels):.3f}  pooled Cllr_min={cllr_min(scores, labels):.3f}"
    )
    if folds:
        c = np.array([f["cllr"] for f in folds])
        cm = np.array([f["cllr_min"] for f in folds])
        au = np.array([f["auc"] for f in folds])
        print(f"  barrel-disjoint over {len(folds)} splits:")
        print(f"    test Cllr     = {c.mean():.3f} +/- {c.std():.3f}")
        print(f"    test Cllr_min = {cm.mean():.3f} +/- {cm.std():.3f}")
        print(f"    test AUC      = {au.mean():.3f} +/- {au.std():.3f}")
        print(f"    calibration loss (Cllr - Cllr_min) = {c.mean() - cm.mean():+.3f}")
    else:
        print("  (too few barrels for a disjoint split)")


def main() -> None:
    results = evaluate_all()
    if not results:
        print("No bullet data — ingest a bullet manifest (e.g. 'hamby-252') first.")
        return
    for res in results:
        _print_study(res)


if __name__ == "__main__":
    main()
