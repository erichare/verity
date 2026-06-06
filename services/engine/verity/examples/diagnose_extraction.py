"""Visual diagnostic for Stage-0 region extraction (:mod:`verity.region`).

Renders, for a single land: the bandpassed surface oriented striae-vertical, the
extracted striae rectangle (groove shoulders cropped from the ends of the long
axis), and the 1-D across-striae signature overlaid. The assessment tool for the
orientation + groove-crop pipeline — run it on any land to eyeball what gets
extracted.

Usage:
    uv run --with matplotlib python -m verity.examples.diagnose_extraction \\
        <study_external_id> <barrel> <bullet> <land_index> <out.png>
"""

from __future__ import annotations

import numpy as np

from verity.examples.hamby_km_knm import LAMBDA_C, LAMBDA_S, read_surface
from verity.preprocess import isolate_roughness, remove_form
from verity.region import extract_region
from verity.surface import Surface


def _bandpassed(surface: Surface) -> np.ndarray:
    s = remove_form(surface)
    s = isolate_roughness(s, LAMBDA_S, LAMBDA_C)
    return s.heights


def plot_extraction(surface: Surface, out_path: str, title: str = "", keep: float = 0.5) -> None:
    """Render the surface (striae vertical) + extracted rectangle + 1-D signature."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    z = _bandpassed(surface)
    w = (~np.isnan(z)).astype(np.float64)
    zr, wr, prof, (lo, hi), tilt = extract_region(z, w, keep=keep)
    disp = np.where(wr > 0.5, zr, np.nan)
    h, width = disp.shape
    fig, ax = plt.subplots(figsize=(12, 6))
    vals = disp[np.isfinite(disp)]
    vmin, vmax = np.percentile(vals, [2, 98]) if len(vals) else (-1, 1)
    ax.imshow(disp, cmap="gray", vmin=vmin, vmax=vmax, aspect="auto", extent=[0, width, h, 0])
    ax.axvspan(0, lo, color="red", alpha=0.25)
    ax.axvspan(hi, width, color="red", alpha=0.25)
    ax.add_patch(plt.Rectangle((lo, 0), hi - lo, h, fill=False, edgecolor="yellow", lw=2.5))
    seg = prof[lo:hi]
    seg = (seg - np.nanmean(seg)) / (np.nanstd(seg) + 1e-9)
    ax.plot(np.arange(lo, hi), h / 2 - seg * h * 0.18, color="cyan", lw=1.3)
    ax.set_title(
        f"{title}  | striae vertical (tilt {tilt:+.0f} deg), "
        f"yellow = extracted region (keep {keep:.0%}), red = grooves"
    )
    ax.set_xlabel("across-striae (long axis)")
    ax.set_ylabel("along striae")
    plt.tight_layout()
    plt.savefig(out_path, dpi=95)
    plt.close()


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
