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
from verity.cmr import areal_votes, consensus_members
from verity.decision import DEFAULT_SCORER_CONFIG
from verity.decision.validation import barrel_disjoint_folds
from verity.examples.hamby_km_knm import _catalog_dir, read_surface

VIRTUAL_KITS_EXTERNAL_ID = "iastate-virtual-kits-30854414"
BREECH_FACE = "breech_face"
_CFG = DEFAULT_SCORER_CONFIG

# Different-source pairs per stratum to keep when scoring (the CMR pass is costly;
# same-source pairs are always kept whole). AUC/Cllr are stable at this size.
MAX_KNM_PER_STRATUM = 500


def cmr_score(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    """The DEPLOYED impressed scorer: the count of congruent matching regions
    (CMR-2d) — local cells that agree on a registration, not one whole-surface
    cross-correlation. Scored exactly as live cartridge comparisons are."""
    members = consensus_members(
        areal_votes(sig_a, sig_b), corr_thresh=_CFG.cmr_corr, transform_tol=_CFG.cmr_tol
    )
    return float(len(members))


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
    marks: list[Mark],
    score_fn: Callable[[np.ndarray, np.ndarray], float],
    *,
    max_knm: int | None = None,
    seed: int = 0,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Stratum]:
    """Bucket all mark-pairs into ``within`` / ``cross`` instrument strata and score them.

    Pairs are bucketed by index first (cheap, no scoring). When ``max_knm`` is set,
    each stratum's different-source pairs are deterministically subsampled to that
    cap (seeded) *before* scoring — so the expensive scorer runs on far fewer pairs
    while the same-source set is kept whole. ``score_fn`` is injected so the
    bucketing is testable without the real scorer; ``on_progress(done, total)``
    fires periodically during scoring.
    """
    # 1. Bucket pair *indices* by stratum (shared instrument?) and class (same firearm?).
    buckets: dict[str, dict[str, list[tuple[int, int]]]] = {
        "within": {"km": [], "knm": []},
        "cross": {"km": [], "knm": []},
    }
    for i, j in combinations(range(len(marks)), 2):
        key = "within" if marks[i][1] == marks[j][1] else "cross"
        cls = "km" if marks[i][0] == marks[j][0] else "knm"
        buckets[key][cls].append((i, j))

    # 2. Optionally cap each stratum's different-source pairs (seeded, stable order).
    rng = np.random.default_rng(seed)
    selected: dict[str, list[tuple[tuple[int, int], int]]] = {}
    for key, cls in buckets.items():
        knm = cls["knm"]
        if max_knm is not None and len(knm) > max_knm:
            keep = sorted(rng.choice(len(knm), size=max_knm, replace=False).tolist())
            knm = [knm[k] for k in keep]
        selected[key] = [(p, 1) for p in cls["km"]] + [(p, 0) for p in knm]

    # 3. Score only the kept pairs.
    total = sum(len(v) for v in selected.values())
    done = 0
    out: dict[str, Stratum] = {}
    for key, pairs in selected.items():
        scores, labels, src_a, src_b = [], [], [], []
        for (i, j), label in pairs:
            scores.append(float(score_fn(marks[i][2], marks[j][2])))
            labels.append(label)
            src_a.append(marks[i][0])
            src_b.append(marks[j][0])
            done += 1
            if on_progress and done % 200 == 0:
                on_progress(done, total)
        out[key] = (np.array(scores), np.array(labels), np.array(src_a), np.array(src_b))
    return out


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


def evaluate(
    marks: list[Mark], score_fn=areal_score, *, max_knm=None, on_progress=None
) -> dict[str, dict]:
    """Score every breech-face pair with ``score_fn`` and summarize the two
    instrument strata (defaults to the global areal CCF). ``max_knm`` caps the
    different-source pairs per stratum so the expensive scorers stay tractable."""
    strata = stratified_pairs(marks, score_fn, max_knm=max_knm, on_progress=on_progress)
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


def _report(name: str, results: dict[str, dict]) -> None:
    """Print one scorer's within/cross strata and its cross-instrument penalty."""
    print(f"  [{name}]")
    for key, label in (("within", "within-instrument"), ("cross", "cross-instrument")):
        r = results[key]
        print(
            f"    {label:17} pairs={r['pairs']:>5} KM={r['km']:>4}  "
            f"AUC={r['auc']:.3f}  Cllr_min={r['cllr_min']:.3f}"
        )
        folds = r["folds"]
        if folds:
            c = np.array([f["cllr"] for f in folds])
            au = np.array([f["auc"] for f in folds])
            print(
                f"      source-disjoint x{len(folds)}: "
                f"Cllr={c.mean():.3f}+/-{c.std():.3f}  AUC={au.mean():.3f}"
            )
    w, x = results["within"], results["cross"]
    if np.isfinite(w["auc"]) and np.isfinite(x["auc"]):
        print(
            f"    -> cross-instrument penalty: AUC {w['auc']:.3f} -> {x['auc']:.3f} "
            f"({x['auc'] - w['auc']:+.3f})\n"
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
    print("  does same-source determination survive a change of 3D imaging system?\n")
    print(
        f"  {len(marks)} breech-face scans, {n_firearms} firearms, "
        f"instruments: {', '.join(instruments)}\n"
    )

    # Two scorers on the SAME (capped) pair set so the head-to-head is fair: the
    # global whole-surface CCF, and the deployed cell-based CMR count. Comparing
    # their cross-instrument penalties shows whether local cell-matching is more
    # robust to an instrument change. KNM pairs are capped per stratum (seeded) so
    # the CMR pass stays tractable; same-source pairs are kept whole.
    def _progress(done: int, total: int) -> None:
        print(f"      scored {done}/{total} pairs", flush=True)

    for name, fn in (
        ("global areal CCF", areal_score),
        ("CMR-2d cell count (deployed)", cmr_score),
    ):
        print(f"  scoring [{name}] (KNM capped at {MAX_KNM_PER_STRATUM}/stratum)...", flush=True)
        _report(name, evaluate(marks, fn, max_knm=MAX_KNM_PER_STRATUM, on_progress=_progress))

    print(
        "  NOTE: the global CCF correlates the whole surface; CMR counts local cells\n"
        "  that independently agree on a registration. A smaller cross-instrument\n"
        "  penalty under CMR would mean local matching survives an instrument change\n"
        "  that whole-surface correlation does not. Different-source pairs are\n"
        "  subsampled per stratum (seeded) for tractability — full-data global numbers\n"
        "  are in PR #120; same-source pairs are kept whole. One consecutively-\n"
        "  controlled set, only the instruments that reach the breech faces; bullets\n"
        "  need strip-aware land extraction (follow-on work)."
    )


if __name__ == "__main__":
    main()
