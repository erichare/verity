"""Does a calibrated same-source determination survive a change of instrument?

The CSAFE *virtual-kits* set (figshare 30854414) scanned the **same** bullets and
cartridge cases on three different 3-D systems — Leeds **Evofinder**, LeadsOnline
**Quantum**, and Cadre **TopMatch**. That makes it the first data in the catalog
that can answer a question casework actually poses: a reference is scanned on one
instrument, the evidence on another — does the weight of evidence hold up?

This runs the deployed impressed-mark metrology (``areal_signature`` + areal
cross-correlation, the same operators the Fadul cartridge proof uses) on the
virtual-kits **breech-face** scans, and splits every pair into two strata:

* **within-instrument** — both scans acquired on the *same* system, and
* **cross-instrument** — the two scans acquired on *different* systems.

Each stratum is scored and characterized on its own (pooled AUC / ``Cllr_min``
plus a source-disjoint ``Cllr`` when the stratum has enough firearms). The
contribution is the *relative* comparison: how much discrimination and
calibration the method loses when the instrument changes. Same-source = same
firearm (the dataset-wide ``firearmID``), source-disjoint by firearm.

Reads the local catalog (no network). Run after the virtual-kits ingest::

    uv run verity-cross-instrument
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import combinations

import numpy as np

from verity import cllr_min, roc_auc
from verity.areal import areal_score, areal_signature
from verity.decision.validation import barrel_disjoint_folds
from verity.examples.hamby_km_knm import _catalog_dir, read_surface

VIRTUAL_KITS_EXTERNAL_ID = "iastate-virtual-kits-30854414"
BREECH_FACE = "breech_face"

# A loaded specimen: its true source firearm, the instrument it was scanned on,
# and its 2-D impressed-mark signature.
Mark = tuple[int, str, np.ndarray]


def load_breech_faces(session, store, study) -> list[Mark]:
    """Every breech-face scan of ``study`` as ``(firearm_id, instrument, sig)``.

    ``firearm_id`` is the dataset-wide source firearm (same id for a gun's bullets
    *and* cartridge cases), so KM = same firearm. The instrument is the 3-D system
    the scan was acquired on, read from the scan's ``Instrument`` link.
    """
    import verity_catalog.models as m
    from sqlmodel import select

    out: list[Mark] = []
    firearms = session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all()
    for firearm in firearms:
        cases = session.exec(
            select(m.CartridgeCase).where(m.CartridgeCase.firearm_id == firearm.id)
        ).all()
        for case in cases:
            marks = session.exec(
                select(m.Mark).where(
                    m.Mark.cartridge_case_id == case.id, m.Mark.mark_type == BREECH_FACE
                )
            ).all()
            for mark in marks:
                scan = session.exec(select(m.Scan).where(m.Scan.mark_id == mark.id)).first()
                if scan is None or scan.instrument_id is None:
                    continue
                instrument = session.get(m.Instrument, scan.instrument_id)
                name = (instrument.external_id if instrument else None) or "unknown"
                surface = read_surface(store.get(scan.content_hash))
                out.append((firearm.id, name, areal_signature(surface)))
    return out


# A scored, labelled, source-tagged pair stratum.
Stratum = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]


def stratified_pairs(
    marks: list[Mark], score_fn: Callable[[np.ndarray, np.ndarray], float]
) -> dict[str, Stratum]:
    """Bucket all mark-pairs into ``within`` / ``cross`` instrument strata.

    Pure over ``score_fn`` (injected so the bucketing is testable without the real
    scorer): each pair contributes its score, KM/KNM label (same firearm?), and
    the two source firearms, to the stratum chosen by whether the two scans share
    an instrument.
    """
    buckets: dict[str, tuple[list, list, list, list]] = {
        "within": ([], [], [], []),
        "cross": ([], [], [], []),
    }
    for (fa, ia, sa), (fb, ib, sb) in combinations(marks, 2):
        key = "within" if ia == ib else "cross"
        scores, labels, src_a, src_b = buckets[key]
        scores.append(float(score_fn(sa, sb)))
        labels.append(1 if fa == fb else 0)
        src_a.append(fa)
        src_b.append(fb)
    return {
        key: (np.array(s), np.array(lb), np.array(a), np.array(b))
        for key, (s, lb, a, b) in buckets.items()
    }


def summarize_stratum(stratum: Stratum) -> dict:
    """Pooled AUC + ``Cllr_min`` and, when foldable, a source-disjoint ``Cllr``."""
    scores, labels, src_a, src_b = stratum
    n_km = int(labels.sum()) if len(labels) else 0
    res: dict = {
        "pairs": int(len(scores)),
        "km": n_km,
        "knm": int(len(scores) - n_km),
        "auc": float(roc_auc(scores, labels)) if n_km and n_km < len(scores) else float("nan"),
        "cllr_min": float(cllr_min(scores, labels))
        if n_km and n_km < len(scores)
        else float("nan"),
        "folds": [],
    }
    # A source-disjoint split needs both classes and several distinct firearms.
    n_sources = len(set(src_a.tolist()) | set(src_b.tolist())) if len(scores) else 0
    if n_km and n_km < len(scores) and n_sources >= 4:
        res["folds"] = barrel_disjoint_folds(scores, labels, src_a, src_b)
    return res


def evaluate(marks: list[Mark]) -> dict[str, dict]:
    """Score every breech-face pair and summarize the two instrument strata."""
    strata = stratified_pairs(marks, areal_score)
    return {key: summarize_stratum(stratum) for key, stratum in strata.items()}


def _load(session_factory=None):
    import verity_catalog.models as m
    from sqlmodel import Session, create_engine, select
    from verity_catalog.store import LocalBlobStore

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    with Session(engine) as session:
        study = session.exec(
            select(m.Study).where(m.Study.external_id == VIRTUAL_KITS_EXTERNAL_ID)
        ).first()
        if study is None:
            return None, None
        marks = load_breech_faces(session, store, study)
    return study, marks


def _fold_line(res: dict) -> str:
    folds = res["folds"]
    if not folds:
        return "    (too few firearms for a source-disjoint split)"
    c = np.array([f["cllr"] for f in folds])
    cm = np.array([f["cllr_min"] for f in folds])
    au = np.array([f["auc"] for f in folds])
    return (
        f"    source-disjoint over {len(folds)} splits: "
        f"Cllr={c.mean():.3f}+/-{c.std():.3f}  Cllr_min={cm.mean():.3f}  AUC={au.mean():.3f}"
    )


def main() -> None:
    study, marks = _load()
    if study is None or not marks:
        print(
            "No virtual-kits breech-face data — ingest it first "
            "(`verity-catalog ingest-virtual-kits`)."
        )
        return

    instruments = sorted({i for _f, i, _s in marks})
    n_firearms = len({f for f, _i, _s in marks})
    print("Cross-instrument validation — virtual-kits breech faces")
    print("  same areal metrology as the Fadul cartridge proof; same-source = same firearm\n")
    print(
        f"  {len(marks)} breech-face scans, {n_firearms} firearms, "
        f"instruments: {', '.join(instruments)}\n"
    )

    results = evaluate(marks)
    for key, label in (("within", "WITHIN-instrument"), ("cross", "CROSS-instrument")):
        r = results[key]
        print(f"  {label}  (pairs={r['pairs']} KM={r['km']} KNM={r['knm']})")
        print(f"    pooled AUC={r['auc']:.3f}  Cllr_min={r['cllr_min']:.3f}")
        print(_fold_line(r))
    w, x = results["within"], results["cross"]
    if np.isfinite(w["auc"]) and np.isfinite(x["auc"]):
        print(
            f"\n  cross-instrument penalty: AUC {w['auc']:.3f} -> {x['auc']:.3f} "
            f"({x['auc'] - w['auc']:+.3f}),  Cllr_min {w['cllr_min']:.3f} -> {x['cllr_min']:.3f}"
        )
    print(
        "\n  NOTE: this is the GLOBAL areal cross-correlation, not the cell-based CMR\n"
        "  count — so a cross-instrument collapse here is a property of the global\n"
        "  scorer (the instrument signature dominates the whole-surface CCF); whether\n"
        "  CMR's local cell matching is more instrument-robust is the natural follow-up.\n"
        "  The finding is the RELATIVE within- vs cross-instrument change on one\n"
        "  consecutively-controlled set (only 2 instruments reach the breech faces).\n"
        "  Bullets need strip-aware land extraction (a whole-bullet strip is not a\n"
        "  single land) and are left to follow-on work."
    )


if __name__ == "__main__":
    main()
