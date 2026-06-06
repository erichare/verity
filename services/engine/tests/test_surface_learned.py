"""Data-gated Phase-2 experiment: the 2-D surface encoder vs CCF, barrel-disjoint.

Like ``test_hamby_learned``, this asserts the experiment *runs* and the CCF
baseline is strong — NOT that the learned representation wins. On ~200 scans per
study it does not (it overfits across barrels, as the 1-D encoder did); the
synthetic ``test_surface_representation`` tests show the 2-D pipeline learns when
given enough signal, so this is a data limit, not a code defect.

Opt in with ``VERITY_HAMBY_TEST=1`` after ingesting the ``hamby-252`` manifest.
"""

import os

import pytest

pytest.importorskip("verity_x3p")
pytest.importorskip("verity_catalog")
pytest.importorskip("torch")


@pytest.mark.skipif(
    not os.environ.get("VERITY_HAMBY_TEST"),
    reason="set VERITY_HAMBY_TEST=1 after ingesting the hamby-252 manifest",
)
def test_surface_encoder_experiment_runs():
    import numpy as np
    import verity_catalog.models as m
    from sqlmodel import Session, create_engine, select
    from verity_catalog.store import LocalBlobStore

    from verity.examples.hamby_km_knm import _catalog_dir
    from verity.examples.surface_learned import SIZE, _cached_features, evaluate_study

    cdir = _catalog_dir()
    cache = cdir / ".verity" / "cache" / f"land{SIZE}"
    cache.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")

    with Session(engine) as session:
        study = session.exec(
            select(m.Study).where(m.Study.external_id == "c09aaa86-5d60-4acb-9031-46dad2c0ad32")
        ).first()
        assert study is not None, "ingest the hamby-252 manifest first"
        bullets = []
        for firearm in session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all():
            for bullet in session.exec(
                select(m.Bullet).where(m.Bullet.firearm_id == firearm.id)
            ).all():
                sigs, imgs = [], []
                for land in session.exec(
                    select(m.Land).where(m.Land.bullet_id == bullet.id).order_by(m.Land.position)
                ).all():
                    scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
                    if scan is None:
                        continue
                    sig, img = _cached_features(store, scan.content_hash, cache)
                    sigs.append(sig)
                    imgs.append(img)
                if sigs:
                    bullets.append((firearm.id, bullet.external_id, sigs, imgs))

    res = evaluate_study(bullets, n_splits=2, seed=0)
    assert res["n_bullets"] >= 30
    folds = res["folds"]
    assert len(folds) >= 1
    for fold in folds:
        for system in ("ccf", "learned"):
            assert np.isfinite(fold[system]["cllr"])
            assert np.isfinite(fold[system]["auc"])
    # CCF discriminates strongly out-of-sample — confirms the harness is sound.
    assert float(np.mean([f["ccf"]["auc"] for f in folds])) > 0.8
