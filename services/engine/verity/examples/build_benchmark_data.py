"""Generate the head-to-head accuracy data for the website's "how accurate is it"
section: **Verity vs the specialist baselines** (bulletxtrctr, CMC/cmcR, Chumbley),
per study, source-disjoint — plus Verity's per-study validation *breadth* across
additional studies that have no published specialist baseline run here.

Every computed number comes from the SAME code paths as the proof scripts
(``verity-firearms-proof`` / ``-cartridge-cmc-proof`` / ``-toolmark-chumbley-proof``)
and the per-study validator (``verity-validate``), with three deliberate choices:

* **Bullets are scored with the production ``diag_contrast`` statistic** — what the
  live engine and the /method page use — not the legacy ``diag_mean`` baked into
  ``firearms_proof`` (``diag_mean`` is the weaker statistic that caused the old
  LR-146 bug). This keeps the head-to-head fair to Verity *and* consistent with the
  breadth table.
* **bulletxtrctr scores are read from the committed cache** (``scores.csv``) rather
  than re-running R — the random forest is the same artifact either way.
* **The deployed cartridge and toolmark figures are QUOTED from the committed frozen
  public benchmarks** (``services/catalog/benchmarks/{cartridge,toolmark}-v1``), not
  recomputed, so /why can never drift from /benchmark, /method, or the registry
  (``docs/headline-numbers.md``). The Ames Lab row is computed here but is a *proof
  scorer* (naive global 1-D CCF, not deployed) and is labeled as such.

Honesty note: these are real, mixed results. The trained specialists lead on their
home sets — bulletxtrctr on bullets, cmcR on Fadul — and the deployed toolmark figure
is the tmaRks benchmark, not the favorable naive-CCF-vs-Chumbley proof run. The point
of the table is generality + calibration, not a clean sweep. Every Verity-side figure
must match a protocol-labeled row in ``docs/headline-numbers.md`` ("Head-to-head vs
specialist baselines").

Re-run (needs the local catalog + R with bulletxtrctr/cmcR/toolmaRk):

    uv --directory services/engine run python -m verity.examples.build_benchmark_data
"""

from __future__ import annotations

import csv
import json
from itertools import combinations
from pathlib import Path

import numpy as np

from verity import roc_auc
from verity.examples.hamby_validation import barrel_disjoint_folds

_ROOT = Path(__file__).resolve().parents[4]
_OUT = _ROOT / "services/web/lib/benchmark-data.json"
_BENCH_DIR = _ROOT / "services/catalog/benchmarks"

# Bullet studies that have a cached bulletxtrctr head-to-head.
_FIREARM_STUDIES = [
    ("Hamby-252", "c09aaa86-5d60-4acb-9031-46dad2c0ad32"),
    ("Prince George's County PD (PGPD) Beretta", "fcafffb1-b96c-49c7-9a9f-b1ec9849f884"),
]

# Per-row scorer labels — the Verity side of every head-to-head row is labeled with
# the scorer/protocol that produced it, matching the registry section
# "Head-to-head vs specialist baselines" in docs/headline-numbers.md.
_BULLET_SCORER = "production CMR-1D (diag_contrast)"
_CARTRIDGE_SCORER = "deployed CMR-2D — frozen benchmark cartridge-v1 (fold mean)"
_TOOLMARK_SCORER = "deployed CMR-1D — frozen benchmark toolmark-v1 (fold mean)"
_AMES_SCORER = "global 1-D CCF — proof scorer, not the deployed CMR-1D"

_BULLET_NOTE = (
    "Same scans, same barrel-disjoint folds, both scorers. The trained specialist "
    "leads on both sets — expected: Verity's bullet contribution is the calibrated, "
    "bounded, deployable LR layer, not a better matcher."
)
_CARTRIDGE_NOTE = (
    "Verity quotes the frozen public benchmark cartridge-v1 (fold mean), per the "
    "cartridge quoting policy in docs/headline-numbers.md; cmcR is the measured "
    "slide-disjoint specialist baseline on the same 190 Fadul pairs, and it leads "
    "on this set."
)
_TOOLMARK_NOTE = (
    "Two distinct datasets: the deployed toolmark figure is the frozen tmaRks "
    "benchmark (toolmark-v1, 56 tool edges). Ames Lab (7 tools, 118 pairs) is a "
    "small proof set the whitepaper calls a weak benchmark for any method, and its "
    "Verity-side scorer is the naive global 1-D CCF, not the deployed pipeline; it "
    "is kept because Chumbley U was run here only on Ames Lab."
)

# A side with no measured competitor (rendered as em-dashes).
_NO_BASELINE = {"cllr": None, "cllrMin": None, "auc": None, "nFolds": 0, "overallAuc": None}


def _r3(x) -> float | None:
    return None if x is None or not np.isfinite(x) else round(float(x), 3)


def _fold_means(folds) -> dict:
    if not folds:
        return {"cllr": None, "cllrMin": None, "auc": None, "nFolds": 0}
    return {
        "cllr": _r3(np.mean([f["cllr"] for f in folds])),
        "cllrMin": _r3(np.mean([f["cllr_min"] for f in folds])),
        "auc": _r3(np.mean([f["auc"] for f in folds])),
        "nFolds": len(folds),
    }


def _side(scores, labels, folds) -> dict:
    """One competitor's row: barrel-disjoint fold means + the pooled overall AUC."""
    fm = _fold_means(folds)
    fm["overallAuc"] = _r3(roc_auc(scores, labels)) if len(scores) else None
    return fm


def _frozen_provenance(split: str) -> dict:
    """The committed frozen-benchmark provenance for ``split`` (e.g. cartridge-v1)."""
    return json.loads((_BENCH_DIR / split / "provenance.json").read_text())


def _frozen_side(prov: dict) -> dict:
    """The frozen benchmark's ``verity_baseline`` as a table side — QUOTED from the
    committed provenance (docs/headline-numbers.md), never recomputed, so the /why
    table cannot drift from /benchmark. ``cllrSd`` carries the registry-mandated ±."""
    vb = prov["verity_baseline"]
    return {
        "cllr": _r3(vb["cllr"]),
        "cllrSd": _r3(vb["cllr_std"]),
        "cllrMin": _r3(vb["cllr_min"]),
        "auc": _r3(vb["auc"]),
        "nFolds": int(vb["n_folds"]),
        "overallAuc": _r3(vb["pooled"]["auc"]),
    }


def _bx_cache(work_dir: Path) -> dict:
    """The committed bulletxtrctr ``scores.csv`` keyed by ``frozenset(bullet ids)``
    (no R rerun — the random forest is the same artifact)."""
    out = work_dir / "scores.csv"
    if not out.exists():
        return {}
    m: dict = {}
    with out.open() as fh:
        for r in csv.DictReader(fh):
            s = r["score"]
            m[frozenset((int(r["bullet_a"]), int(r["bullet_b"])))] = (
                float(s) if s not in ("", "NA") else float("nan")
            )
    return m


def _firearms(session, store, cdir: Path) -> list[dict]:
    import verity_catalog.models as cm
    from sqlmodel import select

    from verity.aggregate import bullet_comparison
    from verity.examples.firearms_proof import load_bullets

    rows = []
    for name, ext in _FIREARM_STUDIES:
        study = session.exec(select(cm.Study).where(cm.Study.external_id == ext)).first()
        if study is None:
            continue
        bullets = load_bullets(session, store, study)
        # Verity = production diag_contrast on each bullet pair.
        vpairs: dict = {}
        for (fa, ida, sa), (fb, idb, sb) in combinations(bullets, 2):
            cmp = bullet_comparison(sa, sb)
            if cmp is None or not np.isfinite(cmp.diag_contrast):
                continue
            vpairs[frozenset((ida, idb))] = (cmp.diag_contrast, 1 if fa == fb else 0, fa, fb)
        bxmap = _bx_cache(cdir / ".verity" / "cache" / "bulletxtrctr" / ext)
        v, b, y, ba, bb = [], [], [], [], []
        for key, (vs, lab, bara, barb) in vpairs.items():
            bs = bxmap.get(key, float("nan"))
            if np.isfinite(vs) and np.isfinite(bs):
                v.append(vs)
                b.append(bs)
                y.append(lab)
                ba.append(bara)
                bb.append(barb)
        v, b, y, ba, bb = (np.array(z) for z in (v, b, y, ba, bb))
        rows.append(
            {
                "study": name,
                "verityScorer": _BULLET_SCORER,
                "nPairs": int(len(y)),
                "nKm": int(y.sum()) if len(y) else 0,
                "nKnm": int((y == 0).sum()) if len(y) else 0,
                "verity": _side(v, y, barrel_disjoint_folds(v, y, ba, bb) if len(y) else []),
                "baseline": _side(b, y, barrel_disjoint_folds(b, y, ba, bb) if len(y) else []),
            }
        )
    return rows


def _cmc_baseline() -> dict:
    """The measured slide-disjoint cmcR specialist baseline on the Fadul pairs
    (the naive areal scores from ``_aligned`` are computed but deliberately unused —
    they are a non-deployed proof scorer and must not be shipped as \"Verity\")."""
    from verity.baselines.cmc import cmc_scores
    from verity.examples.cartridge_cmc_proof import _aligned
    from verity.examples.cartridge_fadul import DEFAULT_CACHE, fetch_fadul, load_marks

    masked = fetch_fadul()
    if masked is None:
        return dict(_NO_BASELINE)
    marks = load_marks(masked)
    cmc_rows = cmc_scores(masked, DEFAULT_CACHE)
    if not cmc_rows:
        return dict(_NO_BASELINE)
    _v, c, y, ga, gb = _aligned(marks, cmc_rows)
    if not len(y):
        return dict(_NO_BASELINE)
    return _side(c, y, barrel_disjoint_folds(c, y, ga, gb))


def _cartridge() -> list[dict]:
    """Fadul head-to-head: the frozen public benchmark (quoted) vs measured cmcR."""
    prov = _frozen_provenance("cartridge-v1")
    counts = prov["counts"]
    return [
        {
            "study": "Fadul 10-slide",
            "verityScorer": _CARTRIDGE_SCORER,
            "nPairs": int(counts["n_pairs"]),
            "nKm": int(counts["n_km"]),
            "nKnm": int(counts["n_knm"]),
            "verity": _frozen_side(prov),
            "baseline": _cmc_baseline(),
        }
    ]


def _ames_proof_row() -> dict | None:
    """The Ames Lab naive-CCF-vs-Chumbley proof run. NOT the deployed pipeline —
    the Verity side is the global 1-D CCF proof scorer and is labeled as such."""
    from verity.baselines.chumbley import chumbley_scores
    from verity.examples.toolmark_ameslab import DEFAULT_CACHE, export_ameslab, load_ameslab_marks
    from verity.examples.toolmark_chumbley_proof import _aligned_arrays

    if not export_ameslab():
        return None
    chumbley = chumbley_scores(DEFAULT_CACHE)
    if not chumbley:
        return None
    marks = load_ameslab_marks()
    v, c, y, ta, tb = _aligned_arrays(marks, chumbley)
    if not len(y):
        return None
    return {
        "study": "Ames Lab screwdrivers",
        "verityScorer": _AMES_SCORER,
        "nPairs": int(len(y)),
        "nKm": int(y.sum()),
        "nKnm": int((y == 0).sum()),
        "verity": _side(v, y, barrel_disjoint_folds(v, y, ta, tb)),
        "baseline": _side(c, y, barrel_disjoint_folds(c, y, ta, tb)),
    }


def _toolmark() -> list[dict]:
    """The deployed tmaRks benchmark figure leads (quoted from the frozen
    provenance; no Chumbley baseline exists on tmaRks here), then the Ames proof row."""
    prov = _frozen_provenance("toolmark-v1")
    counts = prov["counts"]
    rows = [
        {
            "study": "tmaRks 56 tool-edges",
            "verityScorer": _TOOLMARK_SCORER,
            "nPairs": int(counts["n_pairs"]),
            "nKm": int(counts["n_km"]),
            "nKnm": int(counts["n_knm"]),
            "verity": _frozen_side(prov),
            "baseline": dict(_NO_BASELINE),
        }
    ]
    ames = _ames_proof_row()
    if ames is not None:
        rows.append(ames)
    return rows


def _breadth(session, store) -> list[dict]:
    """Verity per-study validation on bullet studies WITHOUT a head-to-head here."""
    from verity.examples.hamby_validation import (
        iter_bullet_studies,
        load_study_bullets,
        pairwise_scores,
    )

    exclude = {ext for _n, ext in _FIREARM_STUDIES}
    out = []
    for study in iter_bullet_studies(session):
        if study.external_id in exclude:
            continue
        bullets = load_study_bullets(session, store, study)
        if not bullets:
            continue
        scores, labels, ba, bb = pairwise_scores(bullets)
        if not len(scores):
            continue
        fm = _fold_means(barrel_disjoint_folds(scores, labels, ba, bb))
        out.append(
            {
                "study": study.title or study.external_id,
                "nBullets": len(bullets),
                "nBarrels": len(set(ba.tolist()) | set(bb.tolist())),
                "nPairs": int(len(scores)),
                "nKm": int(labels.sum()),
                "nKnm": int((labels == 0).sum()),
                "auc": fm["auc"],
                "cllr": fm["cllr"],
                "cllrMin": fm["cllrMin"],
                "overallAuc": _r3(roc_auc(scores, labels)),
                "nFolds": fm["nFolds"],
            }
        )
    return out


def main() -> None:
    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    from verity.examples.hamby_km_knm import _catalog_dir

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    with Session(engine) as session:
        firearms = _firearms(session, store, cdir)
        breadth = _breadth(session, store)
    cartridge = _cartridge()
    toolmark = _toolmark()

    head_to_head = [
        {
            "domain": "Bullet lands",
            "domainTag": "striated",
            "baseline": "bulletxtrctr",
            "baselineNote": "random-forest matchscore · Hare et al. 2017",
            "note": _BULLET_NOTE,
            "studies": firearms,
        },
        {
            "domain": "Cartridge breech faces",
            "domainTag": "impressed",
            "baseline": "CMC (cmcR)",
            "baselineNote": "Congruent Matching Cells · Song 2013",
            "note": _CARTRIDGE_NOTE,
            "studies": cartridge,
        },
        {
            "domain": "Screwdriver toolmarks",
            "domainTag": "striated",
            "baseline": "Chumbley U",
            "baselineNote": "non-random U-statistic · toolmaRk",
            "note": _TOOLMARK_NOTE,
            "studies": toolmark,
        },
    ]
    data = {"headToHead": head_to_head, "breadth": breadth}
    _OUT.write_text(json.dumps(data))
    print(f"wrote {_OUT} ({_OUT.stat().st_size / 1024:.1f} KB)")
    for grp in head_to_head:
        for s in grp["studies"]:
            print(
                f"  {grp['domain']:24s} {s['study']:22s} "
                f"V auc={s['verity']['auc']} cllr={s['verity']['cllr']}  |  "
                f"{grp['baseline']} auc={s['baseline']['auc']} cllr={s['baseline']['cllr']}"
            )
    for s in breadth:
        print(f"  breadth {s['study']:24s} auc={s['auc']} cllr={s['cllr']} cllrMin={s['cllrMin']}")


if __name__ == "__main__":
    main()
