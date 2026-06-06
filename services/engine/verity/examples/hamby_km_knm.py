"""Sanity anchor: on the real Hamby 252 lands, do same-barrel (known-match)
bullet pairs score higher than different-barrel (known-non-match) pairs?

Uses only the Phase-1 primitives (form removal, ISO 16610 bandpass, orientation,
1-D registration). Each land becomes a striation signature; a bullet-to-bullet
score is the best mean land-to-land cross-correlation over cyclic land rotations
(the bulletxtrctr "average of the diagonal").

Run after ingesting the ``hamby-252`` manifest into the catalog::

    cd services/engine && uv pip install -e ".[demo]" && uv run verity-demo-hamby
"""

from __future__ import annotations

import os
import tempfile
from itertools import combinations
from pathlib import Path

import numpy as np

from verity import Surface, striation_signature
from verity.aggregate import bullet_score  # noqa: F401  (re-exported for callers)

# Bandpass cutoffs (metres) for the bullet-striae individualizing band.
LAMBDA_S = float(os.environ.get("VERITY_LAMBDA_S", 4e-6))  # drop measurement noise
LAMBDA_C = float(os.environ.get("VERITY_LAMBDA_C", 250e-6))  # drop waviness/form
# Rotate each land to canonical striae orientation before collapsing (vs. assume
# striae already run along the long axis). Toggle with VERITY_ORIENT=0.
ORIENT = os.environ.get("VERITY_ORIENT", "1") not in ("0", "false", "False")


def _catalog_dir() -> Path:
    env = os.environ.get("VERITY_CATALOG_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "catalog"


def read_surface(data: bytes) -> Surface:
    import verity_x3p

    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        s = verity_x3p.read_x3p(path)
        return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)
    finally:
        Path(path).unlink(missing_ok=True)


# The Hamby-252 study this demo is anchored to (avoids barrel-number collisions
# with other studies once more than one is ingested).
HAMBY_252_EXTERNAL_ID = "c09aaa86-5d60-4acb-9031-46dad2c0ad32"


def load_bullet_signatures(session, store, barrel: int, bullet: int) -> list[np.ndarray]:
    """Striation signatures for the six lands of one bullet, ordered by land."""
    import verity_catalog.models as m
    from sqlmodel import select

    study = session.exec(
        select(m.Study).where(m.Study.external_id == HAMBY_252_EXTERNAL_ID)
    ).first()
    firearm = None
    if study is not None:
        firearm = session.exec(
            select(m.Firearm).where(
                m.Firearm.study_id == study.id,
                m.Firearm.external_id == f"Barrel{barrel}",
            )
        ).first()
    if firearm is None:
        return []
    bullet_row = session.exec(
        select(m.Bullet).where(
            m.Bullet.firearm_id == firearm.id,
            m.Bullet.external_id == f"Barrel{barrel}_Bullet{bullet}",
        )
    ).first()
    if bullet_row is None:
        return []
    lands = session.exec(
        select(m.Land).where(m.Land.bullet_id == bullet_row.id).order_by(m.Land.position)
    ).all()

    signatures = []
    for land in lands:
        scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
        if scan is None:
            continue
        surface = read_surface(store.get(scan.content_hash))
        signatures.append(
            striation_signature(surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C, orient=ORIENT)
        )
    return signatures


def evaluate(barrels: range = range(1, 11)) -> dict:
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")

    with Session(engine) as session:
        b1 = {b: load_bullet_signatures(session, store, b, 1) for b in barrels}
        b2 = {b: load_bullet_signatures(session, store, b, 2) for b in barrels}

    km = [bullet_score(b1[b], b2[b]) for b in barrels if b1.get(b) and b2.get(b)]
    knm = [
        bullet_score(b1[a], b1[b]) for a, b in combinations(barrels, 2) if b1.get(a) and b1.get(b)
    ]
    km = [x for x in km if np.isfinite(x)]
    knm = [x for x in knm if np.isfinite(x)]
    return {"km": km, "knm": knm}


def main() -> None:
    res = evaluate()
    km, knm = res["km"], res["knm"]
    if not km or not knm:
        print("No Hamby data in the catalog — ingest the 'hamby-252' manifest first.")
        return
    print(f"cutoffs: lambda_s={LAMBDA_S * 1e6:.1f} um  lambda_c={LAMBDA_C * 1e6:.0f} um")
    print(f"KM  (same barrel)      n={len(km):3d}  mean={np.mean(km):.3f}  min={np.min(km):.3f}")
    print(f"KNM (different barrel) n={len(knm):3d}  mean={np.mean(knm):.3f}  max={np.max(knm):.3f}")
    sep = float(np.mean(km) - np.mean(knm))
    verdict = "KM > KNM" if sep > 0 else "no separation"
    print(f"separation (mean KM - mean KNM) = {sep:+.3f}  ->  {verdict}")


if __name__ == "__main__":
    main()
