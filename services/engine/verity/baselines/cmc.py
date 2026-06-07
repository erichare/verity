"""Run the Congruent Matching Cells count (cmcR) as a **baseline competitor** for
the cartridge-case head-to-head — the cartridge analog of the bulletxtrctr and
Chumbley adapters, and never in Verity's runtime path.

Shells out to the resumable ``cmc_cartridge.R`` worker, which scores every pair of
the Fadul masked scans and returns the CMC count. The worker is slow (per-pair
cell registration over a rotation grid) but resumable, so a killed run continues.
Requires R with ``cmcR`` (``remotes::install_github("CSAFE-ISU/cmcR")``).
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

_R_SCRIPT = Path(__file__).with_name("cmc_cartridge.R")


def _read(out: Path) -> list[dict]:
    if not out.exists():
        return []
    with out.open() as fh:
        return list(csv.DictReader(fh))


def cmc_scores(masked_dir: Path, cache_dir: Path, *, theta_by: int = 6) -> list[dict]:
    """Per-pair CMC counts ``{i, j, cmc, slide_i, slide_j}`` (i<j, 0-indexed into
    the sorted Fadul file list). Runs/extends the resumable worker if the cache is
    missing or incomplete; empty list if R / ``cmcR`` is unavailable and no cache."""
    out = cache_dir / "cmc_scores.csv"
    n_files = len(sorted(Path(masked_dir).glob("Fadul [0-9]*-[0-9]*.x3p")))
    expected = n_files * (n_files - 1) // 2
    rows = _read(out)
    if len(rows) < expected and shutil.which("Rscript") is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["Rscript", str(_R_SCRIPT), str(masked_dir), str(out), str(theta_by)],
            check=False,
        )
        rows = _read(out)
    return rows
