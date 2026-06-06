"""Does reclaiming the discarded CCF-matrix information widen the KM/KNM margin?

The Phase-1 bullet score is the mean diagonal CCF — one scalar that throws away
the matrix structure (how far the matched diagonal stands above the rest, how far
the winning offset beats the runner-up, whether the per-land lags agree) and the
land-level evidence (six comparisons averaged into one). This harness scores the
same bullet pairs through each reclaimed lever and reports, **barrel-disjoint per
study**, whether it separates the distributions more than the baseline:

* ``diag_mean``      — the Phase-1 baseline (control)
* ``diag_contrast``  — matched diagonal above the matrix background
* ``offset_margin``  — winning land offset above the runner-up
* ``lag_coherence``  — agreement of the per-land alignment lags
* ``diag_min``       — the weakest land along the diagonal
* ``fusion(ΣlogLR)`` — land-level LR fusion (sum of per-land log-LRs)

Every lever is evaluated on identical folds (the split depends only on the
barrels and seed, not the score), so the comparison is apples-to-apples. Reported
metrics: AUC and Cllr_min (discrimination), Cllr (with calibration), and the
margin (Cohen's d, robust percentile gap) — the quantity we are trying to grow.

    uv run verity-margin            # all bullet studies
    uv run verity-margin <guid>     # one study
"""

from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np

from verity.aggregate import bullet_comparison
from verity.decision import ScoreLRModel, cllr, cllr_min, margin, roc_auc
from verity.decision.fusion import LandFusionModel
from verity.examples.hamby_km_knm import (
    LAMBDA_C,
    LAMBDA_S,
    ORIENT,
    _catalog_dir,
    read_surface,
)
from verity.examples.hamby_validation import _resolve_study, iter_bullet_studies
from verity.signature import striation_signature

FEATURES = ("diag_mean", "diag_contrast", "offset_margin", "lag_coherence", "diag_min")


def _sig_cache_dir() -> Path:
    tag = f"ls{LAMBDA_S:g}_lc{LAMBDA_C:g}_o{int(ORIENT)}"
    d = _catalog_dir() / ".verity" / "cache" / "sig" / tag
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cached_signature(store, content_hash: str, cache_dir: Path) -> np.ndarray:
    """Striation signature for a scan, cached by content hash (the same SHA-256
    the catalog uses) so repeated experiment runs are fast and invalidation-free."""
    path = cache_dir / f"{content_hash}.npy"
    if path.exists():
        return np.load(path)
    surface = read_surface(store.get(content_hash))
    sig = striation_signature(surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C, orient=ORIENT)
    np.save(path, sig)
    return sig


def load_bullets(session, store, study, cache_dir) -> list[tuple[int, str, list[np.ndarray]]]:
    """Every bullet of a study as ``(barrel_key, bullet_key, signatures)``, with
    signatures pulled through the content-hash cache."""
    import verity_catalog.models as m
    from sqlmodel import select

    out = []
    for firearm in session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all():
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
                    sigs.append(_cached_signature(store, scan.content_hash, cache_dir))
            if sigs:
                out.append((firearm.id, bullet.external_id, sigs))
    return out


def comparisons(bullets):
    """All bullet-pair comparisons with labels and barrels. Returns
    ``(comps, labels, ba, bb)`` aligned by index."""
    comps, labels, ba, bb = [], [], [], []
    for (ka, _ka, sa), (kb, _kb, sb) in combinations(bullets, 2):
        cmp = bullet_comparison(sa, sb)
        if cmp is None or not np.isfinite(cmp.diag_mean):
            continue
        comps.append(cmp)
        labels.append(1 if ka == kb else 0)
        ba.append(ka)
        bb.append(kb)
    return comps, np.array(labels), np.array(ba), np.array(bb)


def _folds(score_fn, labels, ba, bb, *, n_splits=10, test_frac=0.4, seed=0):
    """Barrel-disjoint folds. ``score_fn(train_mask, test_mask)`` returns the
    ``(train_scores, test_scores)`` for that split — a callable so the fusion
    lever can fit its land calibrator on the training barrels only. Splits depend
    only on barrels + seed, so every lever sees identical folds."""
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
        tr_scores, te_scores = score_fn(in_train, in_test)
        te_lab = labels[in_test]
        lr = ScoreLRModel().fit(tr_scores, labels[in_train]).predict_lr(te_scores)
        m = margin(te_scores, te_lab)
        rows.append(
            {
                "auc": roc_auc(te_scores, te_lab),
                "cllr": cllr(lr[te_lab == 1], lr[te_lab == 0]),
                "cllr_min": cllr_min(te_scores, te_lab),
                "cohens_d": m["cohens_d"],
                "pct_gap": m["pct_gap"],
            }
        )
    return rows


def evaluate_levers(comps, labels, ba, bb) -> dict[str, list[dict]]:
    """Run every lever over the same barrel-disjoint folds."""
    feat = {f: np.array([c.features()[f] for c in comps]) for f in FEATURES}
    diag_ccfs = [c.diag_ccf for c in comps]

    out: dict[str, list[dict]] = {}
    for f in FEATURES:
        out[f] = _folds(lambda tr, te, v=feat[f]: (v[tr], v[te]), labels, ba, bb)

    def fusion_scores(tr, te, method):
        idx = np.where(tr)[0]
        model = LandFusionModel.fit([diag_ccfs[i] for i in idx], labels[tr], method=method)
        fused = model.fused_scores(diag_ccfs)
        return fused[tr], fused[te]

    out["fusion(logit)"] = _folds(lambda tr, te: fusion_scores(tr, te, "logistic"), labels, ba, bb)
    out["fusion(iso)"] = _folds(lambda tr, te: fusion_scores(tr, te, "isotonic"), labels, ba, bb)
    return out


def _mean(rows, key):
    return float(np.mean([r[key] for r in rows])) if rows else float("nan")


def _print_levers(title, n_barrels, n_bullets, labels, levers) -> None:
    print(f"=== {title}  ({n_barrels} barrels, {n_bullets} bullets) ===")
    print(f"  pairs={len(labels)}  KM={int(labels.sum())}  KNM={int((labels == 0).sum())}")
    print(f"  {'lever':<16}{'AUC':>8}{'Cllr':>8}{'Cllr_min':>10}{'cohens_d':>10}{'pct_gap':>9}")
    base = levers.get("diag_mean")
    base_d = _mean(base, "cohens_d") if base else float("nan")
    for name, rows in levers.items():
        if not rows:
            print(f"  {name:<16}  (too few barrels for a disjoint split)")
            continue
        d = _mean(rows, "cohens_d")
        tag = "" if name == "diag_mean" else f"  (margin x{d / base_d:.2f})" if base_d else ""
        print(
            f"  {name:<16}{_mean(rows, 'auc'):>8.3f}{_mean(rows, 'cllr'):>8.3f}"
            f"{_mean(rows, 'cllr_min'):>10.3f}{d:>10.2f}{_mean(rows, 'pct_gap'):>9.2f}{tag}"
        )


def evaluate(study_external_id: str | None = None) -> None:
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    cache_dir = _sig_cache_dir()
    with Session(engine) as session:
        if study_external_id is not None:
            studies = [_resolve_study(session, study_external_id)]
        else:
            studies = iter_bullet_studies(session)
        studies = [s for s in studies if s is not None]
        bundles = [
            (s.title or s.external_id, load_bullets(session, store, s, cache_dir)) for s in studies
        ]

    for title, bullets in bundles:
        if not bullets:
            continue
        comps, labels, ba, bb = comparisons(bullets)
        if not len(labels):
            continue
        n_barrels = len(set(ba.tolist()) | set(bb.tolist()))
        levers = evaluate_levers(comps, labels, ba, bb)
        _print_levers(title, n_barrels, len(bullets), labels, levers)


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    evaluate(arg)


if __name__ == "__main__":
    main()
