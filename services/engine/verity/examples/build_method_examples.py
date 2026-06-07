"""Generate the real per-stage data for the web "How it works" page.

Walks two real Hamby-252 bullet comparisons — one same-firearm (KM), one
different-firearm (KNM) — through the pipeline and dumps every intermediate the
page visualizes (oriented surface, leveled/roughness fields, 1-D signatures, the
alignment lag + matched striae, the KM/KNM reference distributions, the score→LR
curve, and the calibrated result) to ``services/web/lib/method-data.json``.

Hamby/NBTRD bullet scans are public research data, so a downsampled derived
visualization is safe to bundle. Run from anywhere:

    uv --directory /abs/services/engine run python -m verity.examples.build_method_examples
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from verity.compare import _land_fields, _to_preview, compare_bullets_with_previews
from verity.decision.lr import ScoreLRModel, cllr_min
from verity.preprocess import isolate_roughness, remove_form
from verity.registration.align import align_1d
from verity.surface import Surface

_LAMBDA_S, _LAMBDA_C = 4e-6, 250e-6
_ROOT = Path(__file__).resolve().parents[4]
_CACHE = _ROOT / "services/catalog/.verity/cache/bulletxtrctr/c09aaa86-5d60-4acb-9031-46dad2c0ad32"
_REF = _ROOT / "services/api/verity_api/references/bullet_pooled.npz"
_OUT = _ROOT / "services/web/lib/method-data.json"
_GRID = 56  # downsample grids to keep the bundle lean


def _bullets() -> dict[tuple[int, int], list[Path]]:
    by: dict[tuple[int, int], list[tuple[int, Path]]] = defaultdict(list)
    for r in csv.DictReader((_CACHE / "manifest.csv").open()):
        f = _CACHE / "x3p" / f"{r['file']}.x3p"
        if f.exists():
            by[(int(r["barrel"]), int(r["bullet"]))].append((int(r["land"]), f))
    return {k: [f for _, f in sorted(v)] for k, v in sorted(by.items())}


def _surface(path: Path) -> Surface:
    import verity_x3p

    s = verity_x3p.read_x3p(str(path))
    return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)


def _example(a_paths: list[Path], b_paths: list[Path], scores, labels) -> dict:
    surfaces_a = [_surface(p) for p in a_paths]
    surfaces_b = [_surface(p) for p in b_paths]
    report, _previews = compare_bullets_with_previews(
        surfaces_a, surfaces_b,
        reference_scores=scores, reference_labels=labels, reference_name="pooled bullet-land",
    )
    rep = report.to_dict()
    ia = int(rep["provenance"]["best_land_a"])
    ib = int(rep["provenance"]["best_land_b"])

    # Stage intermediates for the strongest-matching land of A (+ its partner in B).
    leveled = remove_form(surfaces_a[ia], degree=2)
    roughness = isolate_roughness(leveled, _LAMBDA_S, _LAMBDA_C)
    sig_a, band_a = _land_fields(surfaces_a[ia])
    sig_b, band_b = _land_fields(surfaces_b[ib])
    lag, _ccf = align_1d(sig_a, sig_b)

    def sig_list(s: np.ndarray) -> list[float]:
        return [round(float(x), 4) for x in np.nan_to_num(s)]

    same = rep["log10_lr"] > 0
    return {
        "sameSource": same,
        "label": "Same firearm" if same else "Different firearms",
        "sublabel": ("two bullets fired from one barrel" if same
                     else "bullets from two different barrels"),
        "scan": _to_preview(band_a, _GRID),  # oriented striae field (3-D)
        "leveled": _to_preview(leveled.heights, _GRID),
        "roughness": _to_preview(roughness.heights, _GRID),
        "signatureA": sig_list(sig_a),
        "signatureB": sig_list(sig_b),
        "lag": int(lag),
        "bandsA": rep["attribution"],
        "bandsB": rep["attribution_b"],
        "score": round(float(rep["score"]), 4),
        "scoreKind": rep["score_kind"],
        "lr": float(rep["likelihood_ratio"]),
        "log10_lr": round(float(rep["log10_lr"]), 3),
        "verbal": rep["verbal"],
        "lrBound": rep["lr_bound_log10"],
        "reference": {
            "name": rep["reference"]["name"], "auc": rep["reference"]["auc"],
            "cllr": rep["reference"]["cllr"], "nKm": rep["reference"]["n_km"],
            "nKnm": rep["reference"]["n_knm"],
        },
    }


def main() -> None:
    rng = np.random.default_rng(0)
    data = np.load(_REF)
    scores, labels = data["scores"], data["labels"]
    bullets = _bullets()
    keys = list(bullets)
    b1 = next(k for k in keys if k[0] == 1)
    b1b = next(k for k in keys if k[0] == 1 and k != b1)
    other = next(k for k in keys if k[0] != 1)
    print(f"KM: {b1} vs {b1b} | KNM: {b1} vs {other}")

    km = _example(bullets[b1], bullets[b1b], scores, labels)
    knm = _example(bullets[b1], bullets[other], scores, labels)

    # Shared calibration context: KM/KNM reference distributions + the score→LR curve.
    def subsample(arr: np.ndarray, n: int) -> list[float]:
        a = arr if arr.size <= n else rng.choice(arr, n, replace=False)
        return [round(float(x), 4) for x in a]

    model = ScoreLRModel(lr_bound="auto").fit(scores, labels)
    lo, hi = float(scores.min()), float(scores.max())
    grid = np.linspace(lo, hi, 90)
    lr_curve = [
        {"score": round(float(s), 4), "lr": float(model.predict_lr(np.array([s]))[0])}
        for s in grid
    ]
    calibration = {
        "km": subsample(scores[labels == 1], 400),
        "knm": subsample(scores[labels == 0], 400),
        "lrCurve": lr_curve,
        "auc": round(float(km["reference"]["auc"]), 3),
        "cllr": round(float(km["reference"]["cllr"]), 3),
        "cllrMin": round(float(cllr_min(scores, labels)), 3),
        "name": km["reference"]["name"],
        "nKm": int(km["reference"]["nKm"]),
        "nKnm": int(km["reference"]["nKnm"]),
    }

    _OUT.write_text(json.dumps({"km": km, "knm": knm, "calibration": calibration}))
    print(f"wrote {_OUT} ({_OUT.stat().st_size / 1024:.0f} KB)")
    print(f"  KM  score={km['score']} LR={km['lr']:.1f} '{km['verbal']}' bands={len(km['bandsA'])}")
    print(f"  KNM score={knm['score']} LR={knm['lr']:.3f} '{knm['verbal']}' bands={len(knm['bandsA'])}")


if __name__ == "__main__":
    main()
