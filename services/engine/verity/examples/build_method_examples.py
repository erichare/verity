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

from verity.cmr import cmr_regions_1d_pair
from verity.compare import _land_fields, _to_preview, compare_bullets_with_previews, compare_with_previews
from verity.decision.lr import ScoreLRModel, cllr_min
from verity.preprocess import isolate_roughness, remove_form
from verity.registration.align import align_1d
from verity.report import build_comparison_report
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
        # Roughness signatures are micron-scale (~1e-6 m); center + scale to ~[-1, 1]
        # so the shape survives rounding (and the plot is amplitude-invariant anyway).
        s = np.nan_to_num(s, nan=0.0)
        s = s - s.mean()
        scale = float(np.max(np.abs(s))) or 1.0
        return [round(float(x / scale), 4) for x in s]

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


def _norm_sig(s) -> list[float]:
    s = np.nan_to_num(np.asarray(s, dtype=float), nan=0.0)
    s = s - s.mean()
    scale = float(np.max(np.abs(s))) or 1.0
    return [round(float(x / scale), 4) for x in s]


def _cartridge_example() -> dict | None:
    """A real Fadul same-slide (KM) breech-face pair → impressed report + previews."""
    from collections import defaultdict

    from verity.examples.cartridge_fadul import _FADUL_RE, _read_surface, fetch_fadul

    masked = fetch_fadul()
    if masked is None:
        return None
    slides: dict[int, list] = defaultdict(list)
    for p in sorted(masked.glob("*.x3p")):
        mm = _FADUL_RE.search(p.name)
        if mm:
            slides[int(mm.group(1))].append(p)
    pair = next((v for v in slides.values() if len(v) >= 2), None)
    if pair is None:
        return None
    ref = np.load(_ROOT / "services/api/verity_api/references/cartridge_fadul.npz")
    report, previews = compare_with_previews(
        _read_surface(pair[0]),
        _read_surface(pair[1]),
        domain="impressed",
        reference_scores=ref["scores"],
        reference_labels=ref["labels"],
        reference_name="Fadul cartridge cases",
        preview_size=72,
    )
    rep = report.to_dict()
    return {
        "domain": "impressed",
        "scanA": previews["a"],
        "scanB": previews["b"],
        "bandsA": rep["attribution"],
        "bandsB": rep["attribution_b"],
        "score": round(float(rep["score"]), 3),
        "lr": float(rep["likelihood_ratio"]),
        "verbal": rep["verbal"],
        "reference": {
            "name": "Fadul cartridge cases (10 consecutively-manufactured slides)",
            "auc": round(float(rep["reference"]["auc"]), 3),
        },
    }


def _screwdriver_example() -> dict | None:
    """A real tmaRks same-tool (KM) screwdriver pair → striated report + matched bands."""
    from collections import defaultdict

    from verity.examples.toolmark_tmaRks import export_tmaRks, load_tmaRks_marks
    from verity.examples.toolmark_transfer import evaluate

    if not export_tmaRks():
        return None
    marks = load_tmaRks_marks(level="edge")
    res = evaluate(marks)
    by: dict[str, list] = defaultdict(list)
    for src, _tid, sig in marks:
        by[src].append(sig)
    pair = next((v for v in by.values() if len(v) >= 2), None)
    if pair is None:
        return None
    sig_a, sig_b = pair[0], pair[1]
    score = float(align_1d(sig_a, sig_b)[1])
    bands_a, bands_b = cmr_regions_1d_pair(sig_a, sig_b, corr_thresh=0.5, lag_tol=10.0)
    report = build_comparison_report(
        score=score,
        reference_scores=res["scores"],
        reference_labels=res["labels"],
        domain="striated",
        reference_name="tmaRks screwdriver toolmarks",
        score_kind="ccf",
    )
    rep = report.to_dict()
    return {
        "domain": "striated",
        "signatureA": _norm_sig(sig_a),
        "signatureB": _norm_sig(sig_b),
        "bandsA": bands_a,
        "bandsB": bands_b,
        "score": round(score, 3),
        "lr": float(rep["likelihood_ratio"]),
        "verbal": rep["verbal"],
        "reference": {"name": "tmaRks screwdriver toolmarks", "auc": round(float(rep["reference"]["auc"]), 3)},
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

    others: dict = {}
    for name, fn in (("cartridge", _cartridge_example), ("screwdriver", _screwdriver_example)):
        try:
            ex = fn()
            if ex:
                others[name] = ex
                print(f"  {name}: LR={ex['lr']:.2f} '{ex['verbal']}'")
            else:
                print(f"  {name}: skipped (data unavailable)")
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: skipped ({exc})")

    out: dict = {"km": km, "knm": knm, "calibration": calibration}
    if others:
        out["others"] = others
    _OUT.write_text(json.dumps(out))
    print(f"wrote {_OUT} ({_OUT.stat().st_size / 1024:.0f} KB)")
    print(f"  KM  score={km['score']} LR={km['lr']:.1f} '{km['verbal']}' bands={len(km['bandsA'])}")
    print(f"  KNM score={knm['score']} LR={knm['lr']:.3f} '{knm['verbal']}' bands={len(knm['bandsA'])}")


if __name__ == "__main__":
    main()
