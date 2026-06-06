"""Materialize algorithmic traces into the catalog (artifacts + DB rows).

    verity-trace [study] [--limit=N] [--no-render]
        Per-land traces: for each land scan, the four-stage trace (raw →
        bandpassed → oriented+cropped → signature) rendered to a PNG and bundled
        as npz, both content-addressed in the artifact store, with a ``ScanTrace``
        row recording the orientation/crop metadata and artifact hashes.

    verity-trace-pairs [study] [--top=N]
        Per-pair diagnostics for the hardest comparisons — the ``N`` worst KM and
        ``N`` best KNM bullet pairs — rendered (CCF matrix + overlays + features)
        and recorded as ``PairDiagnostic`` rows. These are the pairs that carry
        the remaining discrimination headroom.

PNG rendering needs matplotlib:  ``uv run --with matplotlib verity-trace <study>``.
Browsable copies are written under ``<catalog>/.verity/{trace_png,pair_png}/``.
"""

from __future__ import annotations

import io
import sys
import tempfile
from itertools import combinations
from pathlib import Path

import numpy as np

from verity.aggregate import bullet_comparison
from verity.examples.hamby_km_knm import LAMBDA_C, LAMBDA_S, _catalog_dir, read_surface
from verity.examples.hamby_validation import _resolve_study, iter_bullet_studies
from verity.examples.margin_levers import _cached_signature, _sig_cache_dir
from verity.region import DEFAULT_KEEP
from verity.trace import land_trace

PIPELINE_VERSION = "stage0-v1"


def _setup():
    from sqlmodel import create_engine
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    artifacts = LocalBlobStore(cdir / ".verity" / "artifacts")
    return cdir, engine, store, artifacts


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in text)


# --- per-land traces (verity-trace) -----------------------------------------


def _npz_bytes(tr) -> bytes:
    """Light npz bundle — the derived 1-D arrays + crop/angles. The 2-D fields
    are recomputable from the (content-addressed) scan via ``land_trace``."""
    buf = io.BytesIO()
    np.savez_compressed(
        buf,
        signature=tr.signature,
        profile_full=tr.profile_full,
        crop=np.asarray(tr.crop),
        tilt_deg=tr.tilt_deg,
        striae_angle_deg=tr.striae_angle_deg,
    )
    return buf.getvalue()


def trace_scan(session, store, artifacts, scan, *, name, title, png_dir, render):
    """Compute, store, and record one scan's trace. Idempotent per
    ``(scan, pipeline_version)``. Returns ``(row, created)``."""
    import verity_catalog.models as m
    from sqlmodel import select

    existing = session.exec(
        select(m.ScanTrace).where(
            m.ScanTrace.scan_id == scan.id,
            m.ScanTrace.pipeline_version == PIPELINE_VERSION,
        )
    ).first()
    if existing is not None:
        return existing, False

    surface = read_surface(store.get(scan.content_hash))
    tr = land_trace(surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C)
    npz_hash = artifacts.put(_npz_bytes(tr))
    png_hash = _maybe_render(artifacts, png_dir, name, render, lambda p: _render_land(tr, p, title))

    row = m.ScanTrace(
        scan_id=scan.id,
        pipeline_version=PIPELINE_VERSION,
        content_hash_scan=scan.content_hash,
        lambda_s=LAMBDA_S,
        lambda_c=LAMBDA_C,
        degree=2,
        keep=DEFAULT_KEEP,
        orient=True,
        striae_angle_deg=float(tr.striae_angle_deg),
        tilt_deg=float(tr.tilt_deg),
        crop_lo=int(tr.crop[0]),
        crop_hi=int(tr.crop[1]),
        n_signature=int(tr.signature.size),
        png_hash=png_hash,
        npz_hash=npz_hash,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, True


def _render_land(tr, path, title) -> None:
    from verity.viz import render_land_trace

    render_land_trace(tr, path, title=title)


def _maybe_render(artifacts, png_dir, name, render, draw):
    """Run ``draw(tmp_png)``, store the PNG in the artifact store, and mirror a
    browsable copy into ``png_dir``. Returns the artifact hash (or None)."""
    if not render:
        return None
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp = f.name
    try:
        draw(tmp)
        data = Path(tmp).read_bytes()
        png_hash = artifacts.put(data)
        png_dir.mkdir(parents=True, exist_ok=True)
        (png_dir / f"{_slug(name)}.png").write_bytes(data)
        return png_hash
    finally:
        Path(tmp).unlink(missing_ok=True)


def _iter_study_scans(session, study):
    import verity_catalog.models as m
    from sqlmodel import select

    for firearm in session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all():
        for bullet in session.exec(
            select(m.Bullet).where(m.Bullet.firearm_id == firearm.id)
        ).all():
            for land in session.exec(
                select(m.Land).where(m.Land.bullet_id == bullet.id).order_by(m.Land.position)
            ).all():
                scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
                if scan is not None:
                    yield bullet, land, scan


def main() -> None:
    render, limit, rest = True, None, []
    for a in sys.argv[1:]:
        if a == "--no-render":
            render = False
        elif a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
        else:
            rest.append(a)

    from sqlmodel import Session

    cdir, engine, store, artifacts = _setup()
    with Session(engine) as session:
        studies = [_resolve_study(session, rest[0])] if rest else iter_bullet_studies(session)
        for study in [s for s in studies if s is not None]:
            label = study.title or study.external_id
            png_dir = cdir / ".verity" / "trace_png" / _slug(study.external_id)
            n_new = n_skip = 0
            for i, (bullet, land, scan) in enumerate(_iter_study_scans(session, study)):
                if limit is not None and i >= limit:
                    break
                name = f"{bullet.external_id or f'bullet{bullet.id}'}_land{land.position}"
                _, created = trace_scan(
                    session, store, artifacts, scan,
                    name=name, title=f"{label} | {name}", png_dir=png_dir, render=render,
                )
                n_new += int(created)
                n_skip += int(not created)
            dest = png_dir if render else "(no PNG)"
            print(f"{label}: traced {n_new} new, {n_skip} existing -> {dest}")


# --- per-pair diagnostics (verity-trace-pairs) ------------------------------


def _load_bullets_for_pairs(session, store, study, cache_dir):
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
                out.append(
                    {
                        "bullet_id": bullet.id,
                        "firearm_id": firearm.id,
                        "external_id": bullet.external_id or f"bullet{bullet.id}",
                        "sigs": sigs,
                    }
                )
    return out


def _upsert_pair(session, study, a, b, cmp, label, png_hash):
    import verity_catalog.models as m
    from sqlmodel import select

    f = cmp.features()
    existing = session.exec(
        select(m.PairDiagnostic).where(
            m.PairDiagnostic.bullet_a_id == a["bullet_id"],
            m.PairDiagnostic.bullet_b_id == b["bullet_id"],
            m.PairDiagnostic.pipeline_version == PIPELINE_VERSION,
        )
    ).first()
    if existing is not None:
        existing.png_hash = png_hash
        session.add(existing)
        session.commit()
        return
    session.add(
        m.PairDiagnostic(
            study_id=study.id,
            bullet_a_id=a["bullet_id"],
            bullet_b_id=b["bullet_id"],
            pipeline_version=PIPELINE_VERSION,
            label=label,
            offset=int(cmp.offset),
            diag_mean=f["diag_mean"],
            diag_min=f["diag_min"],
            diag_contrast=f["diag_contrast"],
            offset_margin=f["offset_margin"],
            lag_coherence=f["lag_coherence"],
            png_hash=png_hash,
        )
    )
    session.commit()


def pairs_main() -> None:
    top, rest = 5, []
    for a in sys.argv[1:]:
        if a.startswith("--top="):
            top = int(a.split("=", 1)[1])
        else:
            rest.append(a)

    from sqlmodel import Session

    cdir, engine, store, artifacts = _setup()
    cache_dir = _sig_cache_dir()
    with Session(engine) as session:
        studies = [_resolve_study(session, rest[0])] if rest else iter_bullet_studies(session)
        for study in [s for s in studies if s is not None]:
            bullets = _load_bullets_for_pairs(session, store, study, cache_dir)
            pairs = []
            for a, b in combinations(bullets, 2):
                cmp = bullet_comparison(a["sigs"], b["sigs"])
                if cmp is None or not np.isfinite(cmp.diag_mean):
                    continue
                pairs.append((cmp, 1 if a["firearm_id"] == b["firearm_id"] else 0, a, b))

            worst_km = sorted((p for p in pairs if p[1] == 1), key=lambda p: p[0].diag_mean)[:top]
            best_knm = sorted((p for p in pairs if p[1] == 0), key=lambda p: -p[0].diag_mean)[:top]
            png_dir = cdir / ".verity" / "pair_png" / _slug(study.external_id)
            study_label = study.title or study.external_id
            for cmp, label, a, b in worst_km + best_knm:
                tag = "KM" if label else "KNM"
                name = f"{tag}_{a['external_id']}__{b['external_id']}"
                title = f"{study_label} | {tag} | {a['external_id']} vs {b['external_id']}"

                def draw(path, c=cmp, aa=a, bb=b, t=title, lab=label):
                    _render_pair(c, aa, bb, path, t, lab)

                png_hash = _maybe_render(artifacts, png_dir, name, True, draw)
                _upsert_pair(session, study, a, b, cmp, label, png_hash)
            print(
                f"{study.title or study.external_id}: "
                f"{len(worst_km)} worst-KM + {len(best_knm)} best-KNM diagnostics -> {png_dir}"
            )


def _render_pair(cmp, a, b, path, title, label) -> None:
    from verity.viz import render_pair_trace

    render_pair_trace(cmp, a["sigs"], b["sigs"], path, title=title, label=label)


if __name__ == "__main__":
    main()
