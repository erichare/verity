"""Phase 4 — cross-domain transfer demonstrated on the Ames Lab screwdriver
toolmark profiles, the first **non-firearm** dataset Verity is run on.

The dataset is the ``ameslab`` sample shipped with the GPL-3 R package
``toolmaRk`` (Hadler & Morris; Chumbley lineage): 16 striated screwdriver-mark
*profiles* across 7 tools, with same-tool = known-match. Because it is GPL, it is
loaded at runtime from the installed R package and **never vendored into this
MIT repo** — exactly how the ``bulletxtrctr`` baseline is isolated.

The point: each profile is fed through the **same** comparison + decision layer
that did bullet lands — :func:`profile_signature` (1-D form removal + roughness
isolation, the analog of Stage-0 for marks that arrive as profiles) →
``align_1d`` cross-correlation → calibrated, ELUB-bounded LR → **source-disjoint**
``Cllr`` keyed by tool. Zero firearms-specific tuning. Informative transfer
(``Cllr < 1``) is the cross-domain claim — the striae inductive bias carries from
barrels to tools. (Small sample: a proof-of-concept, not a definitive number.)

Requires R with ``toolmaRk`` installed.  Run::

    uv run verity-toolmark-ameslab
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import numpy as np

from verity.examples.toolmark_transfer import Mark, evaluate, profile_signature

DEFAULT_CACHE = Path.home() / ".cache" / "verity" / "ameslab"

# GPL-3 data: read from the installed toolmaRk package, write a neutral CSV cache.
_R_EXPORT = """
data(ameslab, package = "toolmaRk")
cache <- "{cache}"
dir.create(cache, recursive = TRUE, showWarnings = FALSE)
meta <- ameslab[, c("ID", "side", "angle", "rep")]
meta$file <- sprintf("profile_%02d.csv", seq_len(nrow(ameslab)))
write.csv(meta, file.path(cache, "meta.csv"), row.names = FALSE)
for (i in seq_len(nrow(ameslab))) {{
  write.csv(data.frame(v = ameslab$profile[[i]][[1]]),
            file.path(cache, meta$file[i]), row.names = FALSE)
}}
cat("ok\\n")
"""


def export_ameslab(cache: Path = DEFAULT_CACHE, *, force: bool = False) -> bool:
    """Export the GPL ``ameslab`` profiles to a neutral CSV cache outside the repo.
    Returns False if R / ``toolmaRk`` is unavailable."""
    if (cache / "meta.csv").exists() and not force:
        return True
    if shutil.which("Rscript") is None:
        return False
    proc = subprocess.run(
        ["Rscript", "-e", _R_EXPORT.format(cache=cache.as_posix())],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and (cache / "meta.csv").exists()


def load_ameslab_marks(cache: Path = DEFAULT_CACHE, *, waviness: float = 80.0) -> list[Mark]:
    """Marks ``(tool_id, label, signature)``; source = tool ID (ameslab's own
    same-source ground truth — same ID matches across sides and angles)."""
    with (cache / "meta.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    marks: list[Mark] = []
    for row in rows:
        values = np.loadtxt(cache / row["file"], skiprows=1)
        sig = profile_signature(values, waviness=waviness)
        name = f"{row['ID']}{row['side']}_a{row['angle']}_r{row['rep']}"
        marks.append((row["ID"], name, sig))
    return marks


def main() -> None:
    if not export_ameslab():
        print(
            "Could not load ameslab — install R with the 'toolmaRk' package:\n"
            "  install.packages('toolmaRk')   # GPL-3; loaded at runtime, never vendored"
        )
        return
    marks = load_ameslab_marks()
    res = evaluate(marks)
    print("Phase 4 — cross-domain transfer onto Ames Lab screwdriver toolmarks")
    print("  (same Stage-0-less profile signature + CCF + ELUB-bounded LR as bullets)\n")
    from verity.examples.toolmark_transfer import _print

    _print(res)
    print(
        "\n  NOTE: 16 profiles / 7 tools / 15 KM pairs (one tool dominant), KM pairs span\n"
        "  different angles of attack — a small, hard proof-of-concept, not a definitive Cllr."
    )


if __name__ == "__main__":
    main()
