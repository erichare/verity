"""Phase 4 — cross-domain transfer onto non-firearm striated toolmarks.

The claim Verity is built to test: a *domain-general* representation of
individualizing surface texture transfers across forensic modalities. Here we run
the **exact same striated pipeline** that did bullet lands — Stage-0 region
extraction (FFT-orient + groove crop) → 1-D cross-correlation → calibrated,
ELUB-bounded likelihood ratio — on striated **toolmarks** (e.g. consecutively
manufactured screwdrivers), with **zero firearms-specific tuning**. If the
source-disjoint ``Cllr`` is informative, the striae inductive bias generalized
from barrels to tools — the novelty payoff, not a new model.

A *mark* is one striated scan. Its *source* is the tool — or, more precisely, the
tool **working edge** (each side of a flat-head screwdriver tip cuts a distinct
striation pattern), so the source key is whatever ``source_of`` returns.
Source-disjoint folding (no source in train+test) is the barrel-disjoint
discipline, keyed by tool instead of barrel — so the existing
:func:`verity.examples.hamby_validation.barrel_disjoint_folds` is reused verbatim
(it is generic over the grouping key).

Unlike a bullet (6 lands aggregated per comparison), a toolmark is a single mark,
so a pair score is one ``align_1d`` cross-correlation — no land-rotation search.

Run, once the X3P scans are on disk::

    uv run verity-toolmark-transfer <root_dir>
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter1d

from verity import align_1d, cllr_min, roc_auc
from verity.examples.hamby_km_knm import LAMBDA_C, LAMBDA_S, ORIENT, read_surface
from verity.examples.hamby_validation import barrel_disjoint_folds
from verity.signature import striation_signature

# A mark: its source key (tool / tool-edge), a human label, and its 1-D signature.
Mark = tuple[str, str, np.ndarray]


def signature_of(surface, *, keep: float | None = None) -> np.ndarray:
    """The striated signature, with the *same* bandpass + Stage-0 as bullets.

    ``keep`` overrides the Stage-0 groove crop (toolmarks have no groove
    shoulders; ``keep=1.0`` keeps the whole oriented profile). Left ``None`` it
    uses the production default — the honest zero-tuning transfer."""
    kw = {} if keep is None else {"keep": keep}
    return striation_signature(
        surface, lambda_s=LAMBDA_S, lambda_c=LAMBDA_C, orient=ORIENT, **kw
    )


def profile_signature(values, *, deg: int = 2, waviness: float = 80.0) -> np.ndarray:
    """The 1-D analog of :func:`verity.signature.striation_signature` for marks
    that *arrive as profiles* — an already-extracted cross-section, so there is no
    surface to FFT-orient or groove-crop (Stage-0 is the surface→profile step
    these skip). Same logic as the bullet pipeline's form removal + roughness
    isolation, in 1-D: detrend a low-order polynomial (form/curvature), then
    high-pass to drop the residual waviness, leaving the individualizing striae
    residual. ``waviness`` is the high-pass cutoff in samples (0 disables it).

    On the Ames Lab screwdriver profiles this is the difference between chance
    (raw, AUC 0.64) and an informative transfer (AUC 0.82, source-disjoint
    Cllr 0.81) — the same roughness-isolation lesson the bullet lands taught."""
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if len(v) < deg + 2:
        return v - v.mean() if len(v) else v
    x = np.arange(len(v))
    resid = v - np.polyval(np.polyfit(x, v, deg), x)  # remove form (ISO F-operator)
    if waviness and waviness > 0:
        resid = resid - gaussian_filter1d(resid, waviness)  # high-pass: drop waviness
    return resid


def load_marks_from_dir(
    root: str | Path,
    source_of: Callable[[Path], str],
    *,
    glob: str = "**/*.x3p",
    keep: float | None = None,
) -> list[Mark]:
    """Read every X3P under ``root`` into ``(source, name, signature)``.

    ``source_of`` maps a file path to its source key (the tool / tool-edge) — the
    one dataset-specific hook; everything else is the shared pipeline."""
    marks: list[Mark] = []
    for path in sorted(Path(root).glob(glob)):
        surface = read_surface(path.read_bytes())
        sig = signature_of(surface, keep=keep)
        if sig is not None and len(sig) > 0 and np.isfinite(sig).any():
            marks.append((source_of(path), path.name, sig))
    return marks


def mark_pairwise_scores(marks: list[Mark]):
    """All mark-to-mark scores with KM/KNM labels and each side's source key."""
    scores, labels, src_a, src_b = [], [], [], []
    for (sa, _na, siga), (sb, _nb, sigb) in combinations(marks, 2):
        cc = align_1d(siga, sigb)[1]
        if not np.isfinite(cc):
            continue
        scores.append(cc)
        labels.append(1 if sa == sb else 0)
        src_a.append(sa)
        src_b.append(sb)
    return (np.array(scores), np.array(labels), np.array(src_a), np.array(src_b))


def evaluate(marks: list[Mark]) -> dict:
    """Source-disjoint transfer evaluation — same machinery as the bullet proof."""
    scores, labels, sa, sb = mark_pairwise_scores(marks)
    n_sources = len(set(sa.tolist()) | set(sb.tolist())) if len(scores) else 0
    folds = barrel_disjoint_folds(scores, labels, sa, sb) if len(scores) else []
    return {
        "n_marks": len(marks),
        "n_sources": n_sources,
        "scores": scores,
        "labels": labels,
        "folds": folds,
    }


def _print(res: dict) -> None:
    scores, labels, folds = res["scores"], res["labels"], res["folds"]
    print(f"=== toolmark transfer  ({res['n_sources']} sources, {res['n_marks']} marks) ===")
    if not len(scores):
        print("  no scorable mark pairs")
        return
    print(
        f"  pairs={len(scores)}  KM={int(labels.sum())}  KNM={int((labels == 0).sum())}  "
        f"AUC={roc_auc(scores, labels):.3f}  pooled Cllr_min={cllr_min(scores, labels):.3f}"
    )
    if folds:
        c = np.array([f["cllr"] for f in folds])
        cm = np.array([f["cllr_min"] for f in folds])
        au = np.array([f["auc"] for f in folds])
        print(f"  source-disjoint over {len(folds)} splits:")
        print(f"    test Cllr     = {c.mean():.3f} +/- {c.std():.3f}")
        print(f"    test Cllr_min = {cm.mean():.3f} +/- {cm.std():.3f}")
        print(f"    test AUC      = {au.mean():.3f} +/- {au.std():.3f}")
        print(f"    calibration loss (Cllr - Cllr_min) = {c.mean() - cm.mean():+.3f}")
    else:
        print("  (too few sources for a disjoint split)")


def _default_source_of(path: Path) -> str:
    """Fallback grouping: the immediate parent directory (one folder per tool).
    Override with a dataset-specific parser once the file layout is known."""
    return path.parent.name


def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print("usage: verity-toolmark-transfer <root_dir>  (one subfolder per tool source)")
        return
    marks = load_marks_from_dir(sys.argv[1], _default_source_of)
    if not marks:
        print(f"no .x3p scans under {sys.argv[1]!r}")
        return
    _print(evaluate(marks))


if __name__ == "__main__":
    main()
