"""Regenerate the pooled bullet-land reference (``bullet_pooled.npz``) from the local
catalog, *with* barrel cluster IDs and a provenance sidecar.

The shipped reference carried only scores + labels, so the API could not run the honest
*clustered* bootstrap (which resamples whole barrels). This rebuilds it from the catalog
— the four within-study bullet sets (Hamby-252 & 173, PGPD Beretta, Phoenix) — scoring
each bullet pair with the **deployed** ``diag_contrast`` scorer (so the calibration and
the live query score share one scale), and records per-pair barrel IDs + provenance.

KM (same-source) = bullet pairs from the *same* barrel; KNM = bullet pairs from
*different* barrels **within the same study** (no trivial cross-make negatives). Both are
fully enumerated, so the reference is deterministic.

    cd services/engine && uv run python -m verity.examples.build_bullet_pooled_reference [--write]
"""

from __future__ import annotations

import os
import sys
import tempfile
from itertools import combinations
from pathlib import Path

import numpy as np

from verity import Surface
from verity.aggregate import bullet_comparison
from verity.compare import _land_fields
from verity.decision import ContrastScorer

from ._reference_io import write_reference

# The four bullet studies, by catalog external_id (GUIDs / slug), within-study only.
_BULLET_STUDIES = {
    "c09aaa86-5d60-4acb-9031-46dad2c0ad32": "Hamby-252",
    "fcafffb1-b96c-49c7-9a9f-b1ec9849f884": "PGPD-Beretta",
    "bc68296a-f4b0-4afd-b767-4dbfa2961780": "Phoenix-Ruger",
    "b5fbda3e-d889-4211-be7e-654e19b7cd40": "Hamby-173",
}
_ROOT = Path(__file__).resolve().parents[4]
_OUT = _ROOT / "services/api/verity_api/references/bullet_pooled.npz"
_SCORER = ContrastScorer()


def _catalog_dir() -> Path:
    env = os.environ.get("VERITY_CATALOG_DIR")
    return Path(env) if env else _ROOT / "services/catalog"


def _read_surface(data: bytes) -> Surface:
    import verity_x3p

    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        s = verity_x3p.read_x3p(path)
        return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)
    finally:
        Path(path).unlink(missing_ok=True)


def _bullet_signature(surface: Surface) -> np.ndarray:
    """A land's signature via the exact deployed path (so scores match the live API)."""
    return _land_fields(surface)[0]


def _load_bullets() -> dict[str, list[tuple[str, list[np.ndarray]]]]:
    """Map each barrel source-id → list of (bullet_id, [land signatures]) it fired."""
    import verity_catalog.models as m
    from sqlmodel import Session, create_engine, select
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    by_barrel: dict[str, list[tuple[str, list[np.ndarray]]]] = {}
    with Session(engine) as session:
        for ext, _tag in _BULLET_STUDIES.items():
            study = session.exec(select(m.Study).where(m.Study.external_id == ext)).first()
            if study is None:
                print(f"  study {ext} not in catalog — skipping")
                continue
            firearms = session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all()
            for fa in firearms:
                source_id = f"{study.id}:{fa.external_id}"  # globally unique barrel key
                bullets = session.exec(select(m.Bullet).where(m.Bullet.firearm_id == fa.id)).all()
                rows: list[tuple[str, list[np.ndarray]]] = []
                for bl in bullets:
                    lands = session.exec(
                        select(m.Land).where(m.Land.bullet_id == bl.id).order_by(m.Land.position)
                    ).all()
                    sigs: list[np.ndarray] = []
                    for land in lands:
                        scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
                        if scan is None:
                            continue
                        sigs.append(_bullet_signature(_read_surface(store.get(scan.content_hash))))
                    if sigs:
                        rows.append((bl.external_id, sigs))
                if rows:
                    by_barrel.setdefault(source_id, []).extend(rows)
            print(f"  loaded {study.title[:34]:36s} ({_tag})")
    return by_barrel


def _score(sigs_a: list[np.ndarray], sigs_b: list[np.ndarray]) -> float:
    cmp = bullet_comparison(sigs_a, sigs_b)
    return float("nan") if cmp is None else float(_SCORER.score(cmp))


def _cluster_key(src_a: str, src_b: str) -> str:
    return "|".join(sorted((src_a, src_b)))


def build() -> dict:
    by_barrel = _load_bullets()
    barrels = sorted(by_barrel)
    study_of = {b: b.split(":")[0] for b in barrels}
    print(f"{sum(len(v) for v in by_barrel.values())} bullets across {len(barrels)} barrels")

    scores: list[float] = []
    labels: list[int] = []
    clusters: list[str] = []

    # KM: same-barrel bullet pairs.
    for src in barrels:
        for (_, sa), (_, sb) in combinations(by_barrel[src], 2):
            s = _score(sa, sb)
            if np.isfinite(s):
                scores.append(s)
                labels.append(1)
                clusters.append(_cluster_key(src, src))

    # KNM: different-barrel pairs within the same study only.
    for src_a, src_b in combinations(barrels, 2):
        if study_of[src_a] != study_of[src_b]:
            continue
        for (_, sa) in by_barrel[src_a]:
            for (_, sb) in by_barrel[src_b]:
                s = _score(sa, sb)
                if np.isfinite(s):
                    scores.append(s)
                    labels.append(0)
                    clusters.append(_cluster_key(src_a, src_b))

    datasets = [{"external_id": ext, "tag": tag} for ext, tag in _BULLET_STUDIES.items()]
    art = write_reference(
        _OUT,
        scores=np.asarray(scores),
        labels=np.asarray(labels),
        cluster_ids=clusters,
        name="pooled bullet-land reference (Hamby-252 & 173, Beretta, Phoenix)",
        generator="build_bullet_pooled_reference",
        seed=None,  # fully enumerated → deterministic
        datasets=datasets,
        write="--write" in sys.argv,
    )
    d = art.provenance["diagnostics"]
    print(
        f"n_km={d['n_km']} n_knm={d['n_knm']} n_sources={art.provenance['n_sources']} "
        f"AUC={d['auc']:.3f} Cllr={d['cllr']:.3f} Cllr_min={d['cllr_min']:.3f}"
    )
    print(f"{'WROTE' if '--write' in sys.argv else 'DRY-RUN (pass --write to save)'}: {_OUT}")
    return art.provenance


if __name__ == "__main__":
    build()
