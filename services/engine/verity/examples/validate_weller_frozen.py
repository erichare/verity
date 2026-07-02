"""One-shot frozen external validation of the impressed pipeline on the Weller set.

Implements the registered protocol ``docs/weller-preregistration.md`` (OSF:
https://osf.io/prjs9) exactly — nothing here may tune, refit, or re-mask anything:

* **Step 0 integrity gate** — the deployed scorer config and the committed Fadul
  calibration reference must hash to the registered values (§0), or the run aborts.
* **Data** — Weller scans come from the local catalog (study external_id
  ``weller-cartridge-cases``; ``Firearm.external_id`` = the TW slide directory =
  the source; bytes from the catalog blob store). Never from the raw repository.
* **Exclusions (§5.5)** — four mechanical rules, each counted with its trigger:
  unparseable X3P, unattributable to exactly one TW directory, duplicate content
  hash (first kept), and the deployed per-scan scope-guard refusal (mode
  ``refuse``, blocking ``{resolution, modality}``, exactly as the hosted API).
* **Scoring (§2.3)** — the identical code path as the committed reference builder
  (``build_cartridge_fadul_reference``): areal signature → ``areal_votes`` →
  ``consensus_members`` under the frozen scorer config; score = member count.
  A per-pair crash is excluded and counted (§5.6), never retried differently.
* **Calibration** — ``ScoreLRModel(lr_bound="auto")`` fit ONCE on the frozen
  Fadul reference, the exact deployed idiom (``verity/report.py``). No refits.
* **Primary (§5.1)** — pooled Cllr over all scored pairs; H1 supported iff ≤ 0.45.
* **Secondaries (§5.2)** — Cllr_min + calibration loss, pooled AUC of the scores,
  ECE, RMED/RMEP, empirical-cap engagement, scope-refusal counts, and the
  cluster bootstrap over slides (B = 2000, seed 0) on the frozen LRs.
* **Artifacts** — ``docs/whitepaper/data/weller_external.json`` (every count,
  exclusion, metric, interval, hash) + a per-pair ``weller_external_pairs.csv.gz``.

The mechanical protocol itself (exclusion rules, enumeration, scoring path,
calibration, metrics, bootstrap) lives in :mod:`.weller_protocol`, unit-tested on
synthetic data; this module wires it to the catalog and the committed artifacts.

Modes::

    uv run verity-validate-weller                     # THE one-shot registered run
    uv run verity-validate-weller --self-check        # dry-run on the held Fadul set
    uv run verity-validate-weller --build-cartridge-v2  # §5.3 frozen benchmark split

``--self-check`` proves the machinery before the one-shot: it runs the ENTIRE
pipeline on the already-held Fadul scans (the calibration set — explicitly allowed)
and asserts it reproduces the committed reference exactly (190 pairs, 10 KM / 180
KNM, per-pair scores identical to ``cartridge_fadul.npz``). It writes no Weller
artifacts. ``--build-cartridge-v2`` freezes the §5.3 within-study companion
benchmark from the committed one-shot artifacts; it is wired but never run here.

Catalog discovery: the repo-local catalog (``VERITY_CATALOG_DIR``, default
``services/catalog``) like every other example builder, overridable through the
catalog's own settings (``VERITY_CATALOG_DATABASE_URL``,
``VERITY_CATALOG_BLOB_STORE_PATH`` / ``VERITY_CATALOG_BLOB_STORE_BACKEND``).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from collections.abc import Callable
from datetime import date
from itertools import combinations
from pathlib import Path

from verity.benchmark import pair_id

from ._reference_io import LoadedReference, git_short_hash, load_reference
from .build_bullet_pooled_reference import _catalog_dir

# The mechanical protocol (re-exported so tests and callers have one entry point).
from .weller_protocol import (  # noqa: F401 - re-exports are part of this module's API
    ALL_RULES,
    BOOTSTRAP_B,
    BOOTSTRAP_SEED,
    CLLR_H1_THRESHOLD,
    MIN_KM_PAIRS,
    MIN_SCAN_FRACTION,
    N_REGISTERED_SCANS,
    RULE_DUPLICATE,
    RULE_PAIR_CRASH,
    RULE_SCOPE_REFUSAL,
    RULE_UNATTRIBUTABLE,
    RULE_UNPARSEABLE,
    BootstrapCllr,
    Evaluability,
    EvaluableScan,
    Exclusion,
    ProtocolResult,
    ScanRecord,
    _not_evaluable,
    bootstrap_cllr,
    calibrate_frozen,
    check_evaluability,
    compute_metrics,
    deployed_scope_check,
    enumerate_pairs,
    h1_verdict,
    lr_matrix_from,
    replicate_pairs,
    run_protocol,
    score_pair,
    score_pairs,
    screen_scans,
)

_ROOT = Path(__file__).resolve().parents[4]

# ---- §0: the frozen artifacts this run is registered against ---------------- #
FROZEN_SCORER_CONFIG_HASH = "ea4ddd513b57ce8a3dd117dabc6d539432f7ddfab382c425837ead8199a6e127"
FROZEN_REFERENCE_SHA256 = "08133ee1dddc41ea1a9ebb32febb83a785c0b420786d26a404eeb7b8b342ec7c"
REFERENCE_NPZ = _ROOT / "services/api/verity_api/references/cartridge_fadul.npz"

STUDY_EXTERNAL_ID = "weller-cartridge-cases"

# ---- Committed artifact locations (same data dir as other headline numbers) - #
OUT_JSON = _ROOT / "docs/whitepaper/data/weller_external.json"
OUT_PAIRS_CSV = _ROOT / "docs/whitepaper/data/weller_external_pairs.csv.gz"


# --------------------------------------------------------------------------- #
# Step 0 — integrity gate
# --------------------------------------------------------------------------- #
def integrity_gate() -> None:
    """Abort loudly unless the running system is byte-for-byte the registered one."""
    from verity.decision import DEFAULT_SCORER_CONFIG

    got_cfg = DEFAULT_SCORER_CONFIG.config_hash
    if got_cfg != FROZEN_SCORER_CONFIG_HASH:
        raise SystemExit(
            "INTEGRITY GATE FAILED: deployed scorer config hashes to "
            f"{got_cfg} but the registration froze {FROZEN_SCORER_CONFIG_HASH}. "
            "Refusing to run the one-shot on a drifted scorer (§0)."
        )
    got_ref = hashlib.sha256(REFERENCE_NPZ.read_bytes()).hexdigest()
    if got_ref != FROZEN_REFERENCE_SHA256:
        raise SystemExit(
            f"INTEGRITY GATE FAILED: {REFERENCE_NPZ.name} hashes to {got_ref} but the "
            f"registration froze {FROZEN_REFERENCE_SHA256}. Refusing to run (§0)."
        )
    print(f"integrity gate OK: scorer {got_cfg[:12]}…  reference {got_ref[:12]}…")


# --------------------------------------------------------------------------- #
# Catalog loading (Weller) — data loading only, per the no-refit rule (§2.3)
# --------------------------------------------------------------------------- #
def _catalog_engine_and_store():
    """The catalog DB engine + blob store, discovered from the catalog's own config.
    Defaults to the repo-local catalog (like every example builder); any
    ``VERITY_CATALOG_*`` env override (DB URL, store path/backend) wins."""
    from sqlmodel import create_engine
    from verity_catalog.config import get_settings
    from verity_catalog.store import LocalBlobStore, get_store

    settings = get_settings()
    if os.environ.get("VERITY_CATALOG_DATABASE_URL"):
        url = settings.database_url
    else:
        db_path = _catalog_dir() / "verity_catalog.db"
        if not db_path.is_file():  # don't let sqlite silently create an empty catalog
            raise SystemExit(
                f"catalog database not found at {db_path} — set VERITY_CATALOG_DIR or "
                "VERITY_CATALOG_DATABASE_URL to the ingested Weller catalog (§3.4)"
            )
        url = f"sqlite:///{db_path}"
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    if os.environ.get("VERITY_CATALOG_BLOB_STORE_PATH") or settings.blob_store_backend != "local":
        store = get_store(settings)
    else:
        store = LocalBlobStore(_catalog_dir() / ".verity" / "blobs")
    return engine, store


def load_weller_records() -> tuple[list[ScanRecord], Callable[[ScanRecord], bytes]]:
    """Weller scan records from the catalog: Study(external_id =
    ``weller-cartridge-cases``) → Firearm (external_id = TWxx = the source) →
    CartridgeCase → Mark → Scan. Bytes come from the catalog blob store."""
    import verity_catalog.models as m
    from sqlmodel import Session, select

    engine, store = _catalog_engine_and_store()
    records: list[ScanRecord] = []
    with Session(engine) as session:
        study = session.exec(
            select(m.Study).where(m.Study.external_id == STUDY_EXTERNAL_ID)
        ).first()
        if study is None:
            raise SystemExit(
                f"study {STUDY_EXTERNAL_ID!r} is not in the catalog — ingest wellerMasked "
                "first (docs/weller-preregistration.md §3.4)"
            )
        firearms = session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all()
        for fa in firearms:
            source = fa.external_id or None
            cases = session.exec(
                select(m.CartridgeCase).where(m.CartridgeCase.firearm_id == fa.id)
            ).all()
            for case in cases:
                marks = session.exec(
                    select(m.Mark).where(m.Mark.cartridge_case_id == case.id)
                ).all()
                for mark in marks:
                    scans = session.exec(select(m.Scan).where(m.Scan.mark_id == mark.id)).all()
                    for scan in scans:
                        records.append(ScanRecord(
                            source=source,
                            name=scan.filename or scan.content_hash,
                            content_hash=scan.content_hash,
                        ))
    return records, lambda r: store.get(r.content_hash)


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
def result_to_artifact(result: ProtocolResult) -> dict:
    """The committed-artifact JSON: every count, exclusion, metric, interval, and
    the frozen identity of the system that produced them."""
    by_rule = {rule: sum(1 for e in result.exclusions if e.rule == rule) for rule in ALL_RULES}
    scope_reasons = [e.reason for e in result.exclusions if e.rule == RULE_SCOPE_REFUSAL]
    artifact = {
        "study": "Weller et al. (2012) — wellerMasked, slide directories TW01–TW11",
        "protocol": "docs/weller-preregistration.md",
        "registration": "OSF https://osf.io/prjs9 (registered 2026-07-01, before any access)",
        "run": {"git_commit": git_short_hash(), "generated_at": date.today().isoformat(),
                "one_shot": True},
        "frozen": {
            "scorer_config_hash": FROZEN_SCORER_CONFIG_HASH,
            "reference_npz": "services/api/verity_api/references/cartridge_fadul.npz",
            "reference_sha256": FROZEN_REFERENCE_SHA256,
            "score_kind": "cmr-2d",
            "calibration": "ScoreLRModel(lr_bound='auto') fit once on the frozen Fadul "
                           "reference (the deployed report.py idiom); no refits",
            "lr_bound_log10": result.lr_bound_log10,
        },
        "counts": {
            "n_scans_registered": N_REGISTERED_SCANS,
            "n_scans_in_catalog": result.n_records,
            "n_evaluable_scans": len(result.evaluable),
            "n_slides": len({s.record.source for s in result.evaluable}),
            "n_pairs_enumerated": result.n_pairs_enumerated,
            "n_km_enumerated": result.n_km_enumerated,
            "n_pairs_scored": int(len(result.scores)),
            "n_km_scored": int(result.labels.sum()) if result.labels.size else 0,
            "n_knm_scored": int((result.labels == 0).sum()) if result.labels.size else 0,
        },
        "exclusions": {
            "n_total": len(result.exclusions),
            "by_rule": by_rule,
            "scope_refusal_reasons": scope_reasons,
            "detail": [{"rule": e.rule, "item": e.item, "reason": e.reason}
                       for e in result.exclusions],
        },
        "scans": [
            {"source": s.record.source, "name": s.record.name,
             "content_hash": s.record.content_hash}
            for s in result.evaluable
        ],
        "evaluability": {"evaluable": result.evaluability.evaluable,
                         "reasons": list(result.evaluability.reasons)},
        "metrics": result.metrics,
        "bootstrap": None,
        "h1": None,
        "verdict": "not evaluable as registered",
    }
    if result.bootstrap is not None:
        b = result.bootstrap
        artifact["bootstrap"] = {
            "statistic": "pooled Cllr", "resample": "slides (cluster bootstrap)",
            "n_boot": b.n_boot, "seed": b.seed, "ci_lo_2p5": b.lo, "ci_hi_97p5": b.hi,
            "n_used": b.n_used, "n_skipped": b.n_skipped,
        }
    if result.metrics is not None:
        artifact["h1"] = h1_verdict(result.metrics["pooled_cllr"])
        artifact["verdict"] = artifact["h1"]["label"]
    return artifact


def write_artifacts(result: ProtocolResult, *, out_json: Path, out_csv: Path) -> dict:
    artifact = result_to_artifact(result)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(artifact, indent=1) + "\n")
    with gzip.open(out_csv, "wt", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pair_id", "hash_a", "hash_b", "source_a", "source_b",
                         "label", "score", "lr", "bound_hit"])
        rows = zip(result.pairs, result.scores, result.lrs, result.bound_hits, strict=True)
        for p, score, lr, hit in rows:
            writer.writerow([p.pair_id, p.hash_a, p.hash_b, p.source_a, p.source_b,
                             p.label, f"{score:.10g}", f"{lr:.10g}", int(hit)])
    return artifact


def print_summary(result: ProtocolResult, *, title: str) -> None:
    by_rule = {rule: sum(1 for e in result.exclusions if e.rule == rule) for rule in ALL_RULES}
    print(f"\n{title}")
    print(f"  scans: {result.n_records} in catalog → {len(result.evaluable)} evaluable "
          f"(exclusions: {by_rule})")
    print(f"  pairs: {result.n_pairs_enumerated} enumerated "
          f"(KM {result.n_km_enumerated}) → {len(result.scores)} scored")
    if not result.evaluability.evaluable:
        print("  VERDICT: not evaluable as registered — " + "; ".join(
            result.evaluability.reasons))
        return
    m, b = result.metrics, result.bootstrap
    print(f"  pooled Cllr = {m['pooled_cllr']:.4f}  "
          f"(bootstrap 95% [{b.lo:.4f}, {b.hi:.4f}], B={b.n_boot}, seed={b.seed}, "
          f"skipped={b.n_skipped})")
    print(f"  Cllr_min = {m['cllr_min']:.4f}  calibration loss = {m['calibration_loss']:.4f}  "
          f"AUC(scores) = {m['auc_scores']:.4f}  ECE = {m['ece']:.4f}")
    print(f"  RMED = {m['rmed']:.4f}  RMEP = {m['rmep']:.4f}  "
          f"bound-limited = {m['frac_bound_limited']:.4f}")
    verdict = h1_verdict(m["pooled_cllr"])
    outcome = "SUPPORTED" if verdict["supported"] else "NOT SUPPORTED"
    print(f"  H1 (pooled Cllr <= {CLLR_H1_THRESHOLD}): {outcome} — {verdict['label']}")


# --------------------------------------------------------------------------- #
# Modes
# --------------------------------------------------------------------------- #
def _workers() -> int:
    """Process count for the independent per-pair scoring. Defaults to all cores;
    ``VERITY_WELLER_WORKERS`` overrides (1 = serial). Scores are identical either
    way — this is scheduling, not a scorer parameter (§2.2)."""
    override = os.environ.get("VERITY_WELLER_WORKERS", "").strip()
    if override:
        return max(1, int(override))
    return max(1, os.cpu_count() or 1)


def run_weller() -> None:
    """THE one-shot registered run. The first complete execution under the
    registered protocol is the reported result (§2.1)."""
    integrity_gate()
    reference = load_reference(REFERENCE_NPZ)
    records, get_bytes = load_weller_records()
    print(f"catalog: {len(records)} Weller scan rows "
          f"(registered metadata expects {N_REGISTERED_SCANS})")
    result = run_protocol(records, get_bytes, reference=reference, workers=_workers())
    write_artifacts(result, out_json=OUT_JSON, out_csv=OUT_PAIRS_CSV)
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_PAIRS_CSV}")
    print_summary(result, title="Weller external validation — frozen Fadul calibration")


def _fadul_records() -> tuple[list[ScanRecord], Callable[[ScanRecord], bytes]]:
    """The already-held Fadul known-source scans, via the existing
    ``build_cartridge_fadul_reference`` fetch path. Reads NOTHING outside
    ``fadulMasked`` (the Weller set stays untouched until the registered ingest)."""
    from .cartridge_fadul import _FADUL_RE, fetch_fadul

    masked = fetch_fadul()
    if masked is None:
        raise SystemExit("Fadul cache missing — needs git + network once "
                         "(CSAFE-ISU/cartridgeCaseScans)")
    records: list[ScanRecord] = []
    paths: dict[str, Path] = {}
    for path in sorted(masked.glob("*.x3p")):
        m = _FADUL_RE.search(path.name)
        if not m:
            continue  # questioned (single-letter) set — not in the reference either
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append(ScanRecord(source=m.group(1), name=path.stem, content_hash=digest))
        paths[digest] = path
    return records, lambda r: paths[r.content_hash].read_bytes()


def _fadul_reference_scores_by_pair_id(reference: LoadedReference) -> dict[str, float]:
    """The committed reference's per-pair scores keyed by benchmark pair id,
    re-enumerated in the builder's exact order (mirrors ``_cartridge_inputs``)."""
    records, _ = _fadul_records()
    ids = [pair_id(a.content_hash, b.content_hash) for a, b in combinations(records, 2)]
    if len(ids) != len(reference.scores):
        raise SystemExit(
            f"self-check: {len(ids)} enumerated Fadul pairs vs {len(reference.scores)} "
            "in the committed reference — cache and reference disagree"
        )
    return dict(zip(ids, (float(s) for s in reference.scores), strict=True))


def run_self_check() -> None:
    """Dry-run the ENTIRE machinery on the held Fadul set and assert it reproduces
    the committed reference exactly. Writes no Weller artifacts."""
    integrity_gate()
    reference = load_reference(REFERENCE_NPZ)
    records, get_bytes = _fadul_records()
    # Floor thresholds are Weller-registered quantities; Fadul's known counts
    # (40 scans, 10 KM pairs) are asserted directly below instead.
    result = run_protocol(records, get_bytes, reference=reference,
                          n_registered=len(records), min_km_pairs=1, workers=_workers())
    problems: list[str] = []
    if result.exclusions:
        problems.append(f"expected zero exclusions, got {result.exclusions}")
    if len(result.pairs) != 190:
        problems.append(f"expected 190 scored pairs, got {len(result.pairs)}")
    n_km, n_knm = int(result.labels.sum()), int((result.labels == 0).sum())
    if (n_km, n_knm) != (10, 180):
        problems.append(f"expected 10 KM / 180 KNM, got {n_km} / {n_knm}")
    expected = _fadul_reference_scores_by_pair_id(reference)
    got = {p.pair_id: float(s) for p, s in zip(result.pairs, result.scores, strict=True)}
    if sorted(expected) != sorted(got):
        problems.append("pair-id sets diverge from the committed reference")
    else:
        n_bad = sum(1 for pid in expected if expected[pid] != got[pid])
        if n_bad:
            problems.append(f"{n_bad}/190 per-pair scores differ from cartridge_fadul.npz")
    if problems:
        raise SystemExit("SELF-CHECK FAILED:\n  - " + "\n  - ".join(problems))
    print("\nSELF-CHECK PASSED: 190 pairs (10 KM / 180 KNM); per-pair scores identical "
          "to the committed cartridge_fadul.npz (aligned by pair hash).")
    print_summary(result, title="Self-check (Fadul dry-run — NOT the registered result)")


def run_cartridge_v2(out_root: Path | None) -> None:
    """§5.3 companion: freeze the ``cartridge-v2`` (Weller) open-benchmark split
    from the committed one-shot artifacts, under the identical protocol as
    ``cartridge-v1`` (n_splits=10, test_frac=0.4, seed=0, source-disjoint folds,
    LOSO-calibrated Verity baseline WITHIN Weller)."""
    from .build_benchmark_splits import _DEFAULT_OUT, _weller_inputs, build_split

    integrity_gate()
    inputs, scores = _weller_inputs()
    prov = build_split(inputs, out_root or _DEFAULT_OUT, scores=scores)
    c, b = prov["counts"], prov["verity_baseline"]
    print(f"cartridge-v2: pairs={c['n_pairs']} (KM {c['n_km']}) sources={c['n_sources']} "
          f"folds={c['n_folds']} split_hash={prov['split_hash'][:16]}…")
    print(f"  within-Weller baseline: Cllr {b['cllr']:.3f}±{b['cllr_std']:.3f} "
          f"AUC {b['auc']:.3f} calibration loss {b['calibration_loss']:+.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-shot frozen Weller external validation "
                    "(docs/weller-preregistration.md)"
    )
    parser.add_argument("--self-check", action="store_true",
                        help="dry-run the full machinery on the held Fadul set and assert "
                             "it reproduces the committed reference (writes no artifacts)")
    parser.add_argument("--build-cartridge-v2", action="store_true",
                        help="freeze the §5.3 cartridge-v2 benchmark split from the "
                             "committed one-shot artifacts")
    parser.add_argument("--out", type=Path, default=None,
                        help="benchmark output root for --build-cartridge-v2")
    args = parser.parse_args()
    if args.self_check and args.build_cartridge_v2:
        raise SystemExit("pick one mode: --self-check or --build-cartridge-v2")
    if args.self_check:
        run_self_check()
    elif args.build_cartridge_v2:
        run_cartridge_v2(args.out)
    else:
        run_weller()


if __name__ == "__main__":
    main()
