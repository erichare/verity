"""Phase 4 at SCALE — the full CSAFE/tmaRks consecutively-manufactured screwdriver set.

580 striated screwdriver marks from consecutively-manufactured slotted
screwdrivers (heike/tmaRks, MIT) — the same non-firearm domain ameslab sampled,
~40x larger and the dataset behind the Gao/Hofmann/Cuellar 2024 algorithm. Each
mark is a 1-D profile; we run the SAME pipeline as bullets — ``profile_signature``
(1-D form removal + roughness isolation) → ``align_1d`` → calibrated, ELUB-bounded
LR — source-disjoint, with ZERO firearms-specific tuning.

The result hinges on the same-source definition, so we report both:

* **tool-edge** (``T##`` + size + side): the actual mark *generator*. Verity is
  STRONG here — AUC ~0.94 on the full set, ~0.98 on the clean fixed-condition
  block (small tools, one direction/angle); ``Cllr`` ~0.25–0.45.
* **tool** (the two faces merged): cross-edge matching, which is hard — the two
  faces of a flat-head screwdriver cut near-distinct striae → AUC ~0.70. At this
  (coarser) level Verity ties tmaRks's *own* extracted signature (~0.70 vs ~0.71).

The finding: the domain-general pipeline transfers *strongly* to screwdriver
toolmarks when same-source is the mark-generating edge; the tool-level gap is a
real toolmark phenomenon (distinct edges), not a Verity weakness — and Verity
matches the specialist's feature extraction at the level the specialist uses.

Data: ``heike/tmaRks`` ``data/toolmarks.rda`` (MIT), fetched at runtime, cached,
not vendored. Requires R.  Run::

    uv run verity-toolmark-tmaRks
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from collections import OrderedDict
from pathlib import Path

import numpy as np

from verity import cllr_min, roc_auc
from verity.examples.toolmark_transfer import Mark, evaluate, profile_signature

DEFAULT_CACHE = Path.home() / ".cache" / "verity" / "tmaRks"
_RDA_URL = "https://raw.githubusercontent.com/heike/tmaRks/master/data/toolmarks.rda"

_R_FETCH = """
cache <- "{cache}"
dir.create(cache, recursive = TRUE, showWarnings = FALSE)
rda <- file.path(cache, "toolmarks.rda")
if (!file.exists(rda)) download.file("{url}", rda, mode = "wb", quiet = TRUE)
load(rda)
write.csv(toolmarks[, c("TID", "value")],
          file.path(cache, "toolmarks_long.csv"), row.names = FALSE)
cat("ok\\n")
"""


def export_tmaRks(cache: Path = DEFAULT_CACHE) -> bool:
    """Fetch the MIT tmaRks toolmark profiles and write a neutral CSV cache.
    Returns False if R is unavailable."""
    if (cache / "toolmarks_long.csv").exists():
        return True
    if shutil.which("Rscript") is None:
        return False
    proc = subprocess.run(
        ["Rscript", "-e", _R_FETCH.format(cache=cache.as_posix(), url=_RDA_URL)],
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0 and (cache / "toolmarks_long.csv").exists()


def source_key(tid: str, level: str = "edge") -> str:
    """``"T01SA-F80-01"`` → ``"T01SA"`` (edge: tool+size+side, the mark generator)
    or ``"T01S"`` (tool: the two faces merged)."""
    head = tid.split("-")[0]
    return head if level == "edge" else head[:-1]


def load_tmaRks_marks(cache: Path = DEFAULT_CACHE, *, level: str = "edge") -> list[Mark]:
    """Marks ``(source, TID, signature)`` from the cached profiles, grouped by TID
    in file order; source is the tool-edge (default) or tool."""
    grouped: OrderedDict[str, list[float]] = OrderedDict()
    with (cache / "toolmarks_long.csv").open() as fh:
        reader = csv.reader(fh)
        next(reader, None)  # header
        for tid, value in reader:
            grouped.setdefault(tid, []).append(float(value))
    marks: list[Mark] = []
    for tid, values in grouped.items():
        marks.append((source_key(tid, level), tid, profile_signature(np.asarray(values))))
    return marks


def _print(level: str, res: dict) -> None:
    s, y, folds = res["scores"], res["labels"], res["folds"]
    print(
        f"  source={level:9s} marks={res['n_marks']} sources={res['n_sources']} "
        f"pairs={len(s)} KM={int(y.sum())}  AUC={roc_auc(s, y):.3f} "
        f"pooledCllr_min={cllr_min(s, y):.3f}"
    )
    if folds:
        c = np.array([f["cllr"] for f in folds])
        cm = np.array([f["cllr_min"] for f in folds])
        au = np.array([f["auc"] for f in folds])
        print(
            f"      source-disjoint: Cllr={c.mean():.3f}+/-{c.std():.3f} "
            f"Cllr_min={cm.mean():.3f} AUC={au.mean():.3f} "
            f"calib-loss={c.mean() - cm.mean():+.3f} ({len(folds)} folds)"
        )


def main() -> None:
    if not export_tmaRks():
        print("Could not fetch tmaRks — needs R (Rscript) and network access.")
        return
    print("Phase 4 at scale — full tmaRks screwdriver set (same pipeline as bullets):\n")
    for level in ("edge", "tool"):
        _print(level, evaluate(load_tmaRks_marks(level=level)))
    print(
        "\n  edge = the mark generator (tool face); tool = both faces merged.\n"
        "  Strong transfer at the edge level; the tool-level gap is the two faces\n"
        "  cutting near-distinct striae (a real toolmark phenomenon)."
    )


if __name__ == "__main__":
    main()
