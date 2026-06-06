"""Visual diagnostic for the per-land pipeline (a thin CLI over the trace layer).

Renders, for a single land, the full four-panel trace: raw surface → bandpassed
→ FFT-oriented + groove-cropped → 1-D signature (see :mod:`verity.viz.land_trace`
and :mod:`verity.trace`). Run it on any land to eyeball what gets extracted.

Usage:
    uv run --with matplotlib python -m verity.examples.diagnose_extraction \\
        <study_external_id> <barrel> <bullet> <land_index> <out.png>
"""

from __future__ import annotations

from verity.examples.hamby_km_knm import LAMBDA_C, LAMBDA_S, read_surface
from verity.region import DEFAULT_KEEP
from verity.surface import Surface
from verity.trace import land_trace
from verity.viz import render_land_trace


def plot_extraction(
    surface: Surface, out_path: str, title: str = "", keep: float = DEFAULT_KEEP
) -> None:
    """Render the full per-land trace (raw → bandpassed → oriented → signature)."""
    trace = land_trace(surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C, keep=keep)
    render_land_trace(trace, out_path, title=title)


def _load_land(study_ext: str, barrel: int, bullet: int, land_index: int) -> Surface:
    import verity_catalog.models as m
    from sqlmodel import Session, create_engine, select
    from verity_catalog.store import LocalBlobStore

    from verity.examples.hamby_km_knm import _catalog_dir

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    with Session(engine) as session:
        study = session.exec(select(m.Study).where(m.Study.external_id == study_ext)).first()
        firearm = session.exec(
            select(m.Firearm).where(
                m.Firearm.study_id == study.id, m.Firearm.external_id == f"Barrel{barrel}"
            )
        ).first()
        b = session.exec(
            select(m.Bullet).where(
                m.Bullet.firearm_id == firearm.id,
                m.Bullet.external_id == f"Barrel{barrel}_Bullet{bullet}",
            )
        ).first()
        land = session.exec(
            select(m.Land).where(m.Land.bullet_id == b.id).order_by(m.Land.position)
        ).all()[land_index]
        scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
        return read_surface(store.get(scan.content_hash))


def main() -> None:
    import sys

    study_ext, barrel, bullet, land_index, out = sys.argv[1:6]
    surface = _load_land(study_ext, int(barrel), int(bullet), int(land_index))
    plot_extraction(surface, out, title=f"Barrel{barrel} Bullet{bullet} Land{land_index}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
