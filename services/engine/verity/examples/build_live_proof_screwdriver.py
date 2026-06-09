"""Generate the homepage flagship 'Live proof' data from REAL screwdriver toolmarks.

A same-tool-edge (KM) and a different-edge (KNM) tmaRks pair, scored with the deployed
CMR-1D scorer and calibrated on the committed toolmark reference — the two verdicts the
homepage toggle flips between, each with the 1-D signature + congruent-region viz. Writes
``services/web/lib/live-proof-screwdriver.json``. Reproducible from the tmaRks cache + the
committed reference; no network.

    cd services/engine && uv run verity-build-live-proof-screwdriver
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from verity.cmr import cmr_regions_1d_pair, cmr_score_1d
from verity.decision import DEFAULT_SCORER_CONFIG
from verity.examples.toolmark_tmaRks import export_tmaRks, load_tmaRks_marks
from verity.report import build_comparison_report

_CFG = DEFAULT_SCORER_CONFIG
_ROOT = Path(__file__).resolve().parents[4]
_REF = _ROOT / "services/api/verity_api/references/toolmark_tmaRks.npz"
_OUT = _ROOT / "services/web/lib/live-proof-screwdriver.json"

# Fixed, representative pairs: same tool edge (KM) vs two different tool edges (KNM).
_KM = ("T01SB-F80-01", "T01SB-F80-02")
_KNM = ("T01SB-F80-01", "T03LA-F80-01")


def _norm_sig(s: np.ndarray) -> list[float]:
    s = np.nan_to_num(np.asarray(s, dtype=float), nan=0.0)
    s = s - s.mean()
    scale = float(np.max(np.abs(s))) or 1.0
    return [round(float(x / scale), 4) for x in s]


def _example(marks: dict, a_id: str, b_id: str, ref, sublabel: str) -> tuple[dict, dict]:
    sig_a, sig_b = marks[a_id], marks[b_id]
    score = float(cmr_score_1d(sig_a, sig_b, corr_thresh=_CFG.cmr_1d_corr, lag_tol=_CFG.cmr_1d_lag))
    bands_a, bands_b = cmr_regions_1d_pair(
        sig_a, sig_b, corr_thresh=_CFG.cmr_1d_corr, lag_tol=_CFG.cmr_1d_lag
    )
    rep = build_comparison_report(
        score=score,
        reference_scores=ref["scores"],
        reference_labels=ref["labels"],
        domain="striated-toolmark",
        reference_name="tmaRks screwdriver toolmarks",
        score_kind="cmr-1d",
        ci=False,
    ).to_dict()
    example = {
        "sublabel": sublabel,
        "signatureA": _norm_sig(sig_a),
        "signatureB": _norm_sig(sig_b),
        "bandsA": bands_a,
        "bandsB": bands_b,
        "score": round(score, 3),
        "lr": float(rep["likelihood_ratio"]),
        "verbal": rep["verbal"],
    }
    return example, rep["reference"]


def build(write: bool = True) -> dict:
    if not export_tmaRks():
        raise SystemExit("tmaRks cache (or R + network on first fetch) required")
    marks = {tid: sig for _edge, tid, sig in load_tmaRks_marks(level="edge")}
    ref = np.load(_REF, allow_pickle=False)
    km, refdiag = _example(marks, _KM[0], _KM[1], ref, "two marks cut by one screwdriver edge")
    knm, _ = _example(marks, _KNM[0], _KNM[1], ref, "marks from two different screwdriver edges")
    out = {
        "km": km,
        "knm": knm,
        "calibration": {
            "auc": round(float(refdiag["auc"]), 3),
            "cllr": round(float(refdiag["cllr"]), 3),
            "nKm": int(refdiag["n_km"]),
            "nKnm": int(refdiag["n_knm"]),
        },
    }
    print(f"KM  ({_KM[0]} vs {_KM[1]}):  cmr={km['score']:.0f} LR={km['lr']:,.1f} "
          f"'{km['verbal']}' bands={len(km['bandsA'])}")
    print(f"KNM ({_KNM[0]} vs {_KNM[1]}): cmr={knm['score']:.0f} LR={knm['lr']:.3f} "
          f"'{knm['verbal']}' bands={len(knm['bandsA'])}")
    if write:
        _OUT.write_text(json.dumps(out, indent=2) + "\n")
        print(f"WROTE {_OUT}")
    return out


def main() -> None:
    build(write=True)


if __name__ == "__main__":
    main()
