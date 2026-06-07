"""Phase 4 — the striated->impressed crossing, on cartridge-case breech faces.

Verity's central bet is that ONE representation of individualizing surface texture
spans forensic modalities. Bullet lands and toolmarks are striated; a cartridge
case's breech-face impression is **impressed** (2-D), the opposite physics. This
runs the SAME metrology (form removal + ISO roughness isolation) with the areal
comparison (:func:`verity.areal.areal_score`, 2-D cross-correlation over a
rotation grid) on the **Fadul** set: 10 *consecutively-manufactured* pistol
slides x 2 cartridge cases each (the hardest benchmark — the slides are made
back-to-back to be maximally similar). Same-source = same slide, slide-disjoint.

Data: ``CSAFE-ISU/cartridgeCaseScans`` ``fadulMasked/`` (CC-BY 4.0; breech face
pre-masked), fetched at runtime, cached, not vendored. Requires ``git``.  Run::

    uv run verity-cartridge-fadul
"""

from __future__ import annotations

import re
import shutil
import subprocess
from itertools import combinations
from pathlib import Path

import numpy as np

from verity import cllr_min, roc_auc
from verity.areal import areal_score, areal_signature
from verity.examples.hamby_validation import barrel_disjoint_folds
from verity.surface import Surface

DEFAULT_CACHE = Path.home() / ".cache" / "verity" / "cartridgeCaseScans"
_REPO = "https://github.com/CSAFE-ISU/cartridgeCaseScans.git"
_FADUL_RE = re.compile(r"Fadul (\d+)-(\d+)\.x3p$")  # slide-case (known-source only)


def fetch_fadul(cache: Path = DEFAULT_CACHE) -> Path | None:
    """Shallow-clone the CC-BY Fadul scans. Returns the fadulMasked dir, or None
    if git is unavailable."""
    masked = cache / "fadulMasked"
    if masked.exists():
        return masked
    if shutil.which("git") is None:
        return None
    cache.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", _REPO, str(cache)],
        capture_output=True,
        text=True,
    )
    return masked if proc.returncode == 0 and masked.exists() else None


def _read_surface(path: Path) -> Surface:
    import verity_x3p

    s = verity_x3p.read_x3p(str(path))
    return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)


def load_marks(masked_dir: Path):
    """``(slide, name, areal_signature)`` for every known-source Fadul scan."""
    marks = []
    for path in sorted(masked_dir.glob("*.x3p")):
        m = _FADUL_RE.search(path.name)
        if not m:
            continue  # skip the questioned (single-letter) set
        marks.append((int(m.group(1)), path.stem, areal_signature(_read_surface(path))))
    return marks


def evaluate(marks):
    scores, labels, sa, sb = [], [], [], []
    for (slide_a, _na, sig_a), (slide_b, _nb, sig_b) in combinations(marks, 2):
        scores.append(areal_score(sig_a, sig_b))
        labels.append(1 if slide_a == slide_b else 0)
        sa.append(slide_a)
        sb.append(slide_b)
    scores, labels = np.array(scores), np.array(labels)
    folds = barrel_disjoint_folds(scores, labels, np.array(sa), np.array(sb)) if len(scores) else []
    return scores, labels, folds


def main() -> None:
    masked = fetch_fadul()
    if masked is None:
        print("Could not fetch Fadul scans — needs git + network (CSAFE-ISU/cartridgeCaseScans).")
        return
    marks = load_marks(masked)
    n_slides = len({s for s, _n, _g in marks})
    print("Phase 4 — striated->impressed crossing on Fadul cartridge cases")
    print("  (same form-removal + roughness isolation as bullets; areal CCF over rotation)\n")
    scores, labels, folds = evaluate(marks)
    print(f"  {len(marks)} scans, {n_slides} slides  pairs={len(scores)} "
          f"KM={int(labels.sum())} KNM={int((labels == 0).sum())}")
    print(f"  pooled AUC={roc_auc(scores, labels):.3f}  Cllr_min={cllr_min(scores, labels):.3f}")
    if folds:
        c = np.array([f["cllr"] for f in folds])
        au = np.array([f["auc"] for f in folds])
        cm = np.array([f["cllr_min"] for f in folds])
        print(f"  slide-disjoint over {len(folds)} splits: "
              f"Cllr={c.mean():.3f}+/-{c.std():.3f} Cllr_min={cm.mean():.3f} AUC={au.mean():.3f}")
    print(
        "\n  NOTE: 10 consecutively-manufactured slides / 10 KM pairs — the hardest,\n"
        "  smallest cartridge benchmark. A proof the metrology crosses to impressed\n"
        "  marks, not a definitive Cllr."
    )


if __name__ == "__main__":
    main()
