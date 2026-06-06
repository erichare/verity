"""Run the bulletxtrctr (R) bullet-comparison pipeline as a **baseline
competitor** in Verity's validation harness — never in Verity's runtime path.

Dumps a study's x3p lands (named by content hash, so signatures cache across
runs), writes a manifest, and shells out to ``bulletxtrctr_score.R``, which
returns bullet-to-bullet random-forest matchscores. Requires R with
``bulletxtrctr``, ``x3ptools``, ``randomForest`` installed.
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

_R_SCRIPT = Path(__file__).with_name("bulletxtrctr_score.R")


def dump_study_lands(session, store, study, x3p_dir: Path) -> list[dict]:
    """Write each land's x3p to ``x3p_dir/{hash}.x3p`` and return manifest rows
    ``{file, barrel, bullet, land}`` keyed by globally-unique firearm/bullet ids."""
    import verity_catalog.models as m
    from sqlmodel import select

    x3p_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for firearm in session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all():
        for bullet in session.exec(select(m.Bullet).where(m.Bullet.firearm_id == firearm.id)).all():
            lands = session.exec(
                select(m.Land).where(m.Land.bullet_id == bullet.id).order_by(m.Land.position)
            ).all()
            for pos, land in enumerate(lands):
                scan = session.exec(select(m.Scan).where(m.Scan.land_id == land.id)).first()
                if scan is None:
                    continue
                dest = x3p_dir / f"{scan.content_hash}.x3p"
                if not dest.exists():
                    dest.write_bytes(store.get(scan.content_hash))
                rows.append(
                    {
                        "file": scan.content_hash,
                        "barrel": firearm.id,
                        "bullet": bullet.id,
                        "land": pos,
                    }
                )
    return rows


def run_bulletxtrctr(rows: list[dict], work_dir: Path) -> list[dict]:
    """Run the R worker over the manifest ``rows``; return bullet-pair scores
    ``{barrel_a, bullet_a, barrel_b, bullet_b, score}``."""
    work_dir.mkdir(parents=True, exist_ok=True)
    manifest = work_dir / "manifest.csv"
    out = work_dir / "scores.csv"
    with manifest.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["file", "barrel", "bullet", "land"])
        writer.writeheader()
        writer.writerows(rows)

    subprocess.run(
        [
            "Rscript",
            str(_R_SCRIPT),
            str(manifest),
            str(work_dir / "x3p"),
            str(work_dir / "sig_cache"),
            str(out),
        ],
        check=True,
    )

    with out.open() as fh:
        return [
            {
                "barrel_a": int(r["barrel_a"]),
                "bullet_a": int(r["bullet_a"]),
                "barrel_b": int(r["barrel_b"]),
                "bullet_b": int(r["bullet_b"]),
                "score": float(r["score"]) if r["score"] not in ("", "NA") else float("nan"),
            }
            for r in csv.DictReader(fh)
        ]


def bulletxtrctr_scores(session, store, study, work_dir: Path) -> list[dict]:
    """End-to-end: dump a study's lands and score every bullet pair with bulletxtrctr."""
    rows = dump_study_lands(session, store, study, work_dir / "x3p")
    return run_bulletxtrctr(rows, work_dir)
