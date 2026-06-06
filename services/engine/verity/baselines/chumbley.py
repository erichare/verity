"""Run the Chumbley toolmark U-statistic (R, ``toolmaRk::chumbley_non_random``)
as a **baseline competitor** for the Phase-4 toolmark head-to-head — the toolmark
analog of the ``bulletxtrctr`` adapter, and never in Verity's runtime path.

Shells out to ``chumbley_toolmark.R``, which scores every pair of the GPL
``ameslab`` profiles and returns the U statistic + p-value. Results are cached
(the per-pair optimization is the slow part). Requires R with ``toolmaRk``.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

_R_SCRIPT = Path(__file__).with_name("chumbley_toolmark.R")


def chumbley_scores(cache_dir: Path, *, force: bool = False) -> list[dict]:
    """Per-pair Chumbley results ``{i, j, U, p_value, id_i, id_j}`` (i<j, 0-indexed
    into the ameslab row order). Empty list if R / ``toolmaRk`` is unavailable."""
    out = cache_dir / "chumbley_scores.csv"
    if force or not out.exists():
        if shutil.which("Rscript") is None:
            return []
        cache_dir.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["Rscript", str(_R_SCRIPT), str(out)], capture_output=True, text=True
        )
        if proc.returncode != 0 or not out.exists():
            return []
    with out.open() as fh:
        return list(csv.DictReader(fh))
