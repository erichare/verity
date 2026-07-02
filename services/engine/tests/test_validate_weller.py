"""The registered Weller one-shot driver (``validate_weller_frozen``), on synthetic
data only — no Weller data, no network, no catalog.

Covers the §5.5 exclusion rules, the §4 pair enumeration/labeling expectation
(9×10 + 5 scans ⇒ 4 465 pairs / 370 KM), the evaluability floor, the §5.2
cluster-bootstrap mechanics (copies-of-same-slide KM rule, self-pair exclusion,
seed determinism, skip counting), and the calibration-parity claim against the
deployed ``build_comparison_report`` idiom.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import verity.examples.validate_weller_frozen as vw
from verity.decision.scope_guard import ScopeReport
from verity.examples._reference_io import LoadedReference
from verity.report import build_comparison_report


def _hash(i: int) -> str:
    return f"{i:064x}"


def _record(i: int, source: str | None = "TW01", name: str | None = None) -> vw.ScanRecord:
    return vw.ScanRecord(source=source, name=name or f"scan-{i:02d}", content_hash=_hash(i))


def _admissible(admissible: bool = True, reason: str = "") -> ScopeReport:
    return ScopeReport(admissible=admissible, mode="refuse", domain="impressed",
                       checks=[], overall_reason=reason)


def _screen(records, *, get_bytes=None, scope=None):
    """Run screen_scans with trivial fakes (no real surfaces or signatures)."""
    return vw.screen_scans(
        records,
        get_bytes=get_bytes or (lambda r: b"bytes"),
        read_surface=lambda data: object(),
        scope_check=scope or (lambda surface: _admissible()),
        make_signature=lambda surface: np.zeros((2, 2)),
    )


# --------------------------------------------------------------------------- #
# §4 — enumeration and labeling
# --------------------------------------------------------------------------- #
def test_registered_expectation_95_scans_4465_pairs_370_km():
    """9 scans in each of TW01..TW10 plus 5 in TW11 ⇒ C(95,2)=4465 pairs, 370 KM."""
    counts = [9] * 10 + [5]
    records, i = [], 0
    for slide, n in enumerate(counts, start=1):
        for _ in range(n):
            records.append(_record(i, source=f"TW{slide:02d}"))
            i += 1
    pairs, idx = vw.enumerate_pairs(records)
    labels = [p.label for p in pairs]
    assert len(pairs) == 4465
    assert sum(labels) == 370
    assert len(idx) == 4465
    assert all(i < j for i, j in idx)


def test_pair_labels_km_iff_same_source():
    records = [_record(0, "TW01"), _record(1, "TW01"), _record(2, "TW02")]
    pairs, _ = vw.enumerate_pairs(records)
    assert [p.label for p in pairs] == [1, 0, 0]
    km = pairs[0]
    assert km.source_a == km.source_b == "TW01"


# --------------------------------------------------------------------------- #
# §5.5 — exclusion rules, each mechanical and counted
# --------------------------------------------------------------------------- #
def test_rule1_unparseable_is_excluded_and_counted():
    records = [_record(0), _record(1)]

    def get_bytes(r):
        if r.content_hash == _hash(0):
            raise ValueError("bad zip")
        return b"ok"

    kept, excluded = _screen(records, get_bytes=get_bytes)
    assert [s.record.content_hash for s in kept] == [_hash(1)]
    assert [e.rule for e in excluded] == [vw.RULE_UNPARSEABLE]
    assert "bad zip" in excluded[0].reason


def test_rule2_unattributable_no_source():
    kept, excluded = _screen([_record(0, source=None), _record(1)])
    assert [s.record.content_hash for s in kept] == [_hash(1)]
    assert [e.rule for e in excluded] == [vw.RULE_UNATTRIBUTABLE]


def test_rule2_unattributable_content_under_two_directories():
    """The same content hash under two TW directories is assignable to neither."""
    records = [
        vw.ScanRecord(source="TW01", name="a", content_hash=_hash(7)),
        vw.ScanRecord(source="TW02", name="b", content_hash=_hash(7)),
        _record(1, "TW03"),
    ]
    kept, excluded = _screen(records)
    assert [s.record.content_hash for s in kept] == [_hash(1)]
    assert [e.rule for e in excluded] == [vw.RULE_UNATTRIBUTABLE] * 2


def test_rule3_duplicate_first_kept():
    records = [
        vw.ScanRecord(source="TW01", name="first", content_hash=_hash(7)),
        vw.ScanRecord(source="TW01", name="second", content_hash=_hash(7)),
    ]
    kept, excluded = _screen(records)
    assert [s.record.name for s in kept] == ["first"]
    assert [(e.rule, e.item) for e in excluded] == [(vw.RULE_DUPLICATE, "second")]


def test_rule4_scope_refusal_records_reason():
    records = [_record(0), _record(1)]

    def scope(surface):
        # Refuse exactly one scan: the fakes make surfaces indistinguishable, so
        # key off call order via a mutable cell.
        calls.append(1)
        if len(calls) == 1:
            return _admissible(False, "lateral pitch 5.00 µm exceeds λ_s")
        return _admissible()

    calls: list[int] = []
    kept, excluded = _screen(records, scope=scope)
    assert len(kept) == 1
    assert [e.rule for e in excluded] == [vw.RULE_SCOPE_REFUSAL]
    assert "λ_s" in excluded[0].reason


def test_rules_apply_in_registered_order():
    """A scan failing several rules is counted under the first (parse before
    attribution before dedup before scope)."""
    records = [
        vw.ScanRecord(source=None, name="unparseable-and-unattributable", content_hash=_hash(0)),
        vw.ScanRecord(source="TW01", name="kept", content_hash=_hash(1)),
        vw.ScanRecord(source="TW01", name="dup-and-refused", content_hash=_hash(1)),
    ]

    def get_bytes(r):
        if r.name == "unparseable-and-unattributable":
            raise OSError("truncated")
        return b"ok"

    kept, excluded = _screen(records, get_bytes=get_bytes,
                             scope=lambda s: _admissible(False, "refused"))
    # "kept" itself is then refused by the scope guard (rule 4).
    assert [e.rule for e in excluded] == [
        vw.RULE_UNPARSEABLE, vw.RULE_SCOPE_REFUSAL, vw.RULE_DUPLICATE
    ]
    assert not kept


def test_signature_crash_counts_under_rule1_semantics():
    records = [_record(0)]

    def boom(surface):
        raise RuntimeError("degenerate grid")

    kept, excluded = vw.screen_scans(
        records, get_bytes=lambda r: b"", read_surface=lambda d: object(),
        scope_check=lambda s: _admissible(), make_signature=boom,
    )
    assert not kept
    assert [e.rule for e in excluded] == [vw.RULE_UNPARSEABLE]
    assert "signature" in excluded[0].reason


# --------------------------------------------------------------------------- #
# §5.6 — per-pair crash handling
# --------------------------------------------------------------------------- #
def test_pair_crash_is_excluded_and_counted_never_retried():
    records = [_record(i, "TW01") for i in range(3)]
    evaluable = tuple(vw.EvaluableScan(record=r, signature=np.full((2, 2), i))
                      for i, r in enumerate(records))
    pairs, idx = vw.enumerate_pairs(records)
    attempts: list[tuple[float, float]] = []

    def score_fn(a, b):
        attempts.append((float(a[0, 0]), float(b[0, 0])))
        if float(b[0, 0]) == 2.0:
            raise RuntimeError("solver crash")
        return 5.0

    scores, excluded = vw.score_pairs(evaluable, pairs, idx, score_fn=score_fn)
    assert np.isnan(scores[[1, 2]]).all() and scores[0] == 5.0
    assert [e.rule for e in excluded] == [vw.RULE_PAIR_CRASH] * 2
    assert len(attempts) == 3  # one attempt per pair — never retried


# --------------------------------------------------------------------------- #
# §5.5 — evaluability floor
# --------------------------------------------------------------------------- #
def test_floor_scan_fraction():
    assert not vw.check_evaluability(47, 370).evaluable  # 47 < 47.5 = 50% of 95
    assert vw.check_evaluability(48, 370).evaluable


def test_floor_km_pairs():
    bad = vw.check_evaluability(95, 29)
    assert not bad.evaluable and "29 same-source pairs" in bad.reasons[0]
    assert vw.check_evaluability(95, 30).evaluable


def test_floor_reports_both_reasons():
    ev = vw.check_evaluability(10, 3)
    assert not ev.evaluable and len(ev.reasons) == 2


# --------------------------------------------------------------------------- #
# §5.2 — cluster-bootstrap mechanics
# --------------------------------------------------------------------------- #
def test_replicate_pairs_same_slide_copies_are_km_and_self_pairs_drop():
    """Draw [A, A, B] with A = scans {0, 1}, B = {2}: cross-copy pairs of the same
    slide are KM; a scan never pairs with itself."""
    a, b, km = vw.replicate_pairs(["A", "A", "B"], {"A": [0, 1], "B": [2]})
    got = sorted(zip(a.tolist(), b.tolist(), km.tolist(), strict=True))
    # Positions [0,1,0,1,2]: 10 position-pairs, minus the two (0,0)/(1,1) self-pairs.
    assert len(got) == 8
    assert sum(1 for _, _, k in got if k) == 4  # (0,1) ×3 within/between A copies + (1,0)
    assert all(x != y for x, y, _ in got)
    assert all(k for x, y, k in got if {x, y} == {0, 1})  # every A–A pair is KM
    assert not any(k for x, y, k in got if 2 in (x, y))  # every A–B pair is KNM


def test_replicate_pairs_single_scan_slide_has_no_pairs():
    a, b, km = vw.replicate_pairs(["A", "A", "A"], {"A": [0]})
    assert a.size == b.size == km.size == 0


def _toy_lr_matrix():
    """6 slides × 2 scans; KM pairs get LRs > 1, KNM pairs LRs < 1, each varying
    by pair so replicate composition moves the pooled Cllr. (Six slides keep the
    chance of a degenerate all-one-slide replicate negligible.)"""
    sources = [s for s in "ABCDEF" for _ in range(2)]
    n = len(sources)
    rng = np.random.default_rng(42)
    matrix = np.full((n, n), np.nan)
    for i in range(n):
        for j in range(i + 1, n):
            same = sources[i] == sources[j]
            lr = rng.uniform(2.0, 40.0) if same else rng.uniform(0.02, 0.9)
            matrix[i, j] = matrix[j, i] = lr
    return sources, matrix


def test_bootstrap_seed_determinism():
    sources, matrix = _toy_lr_matrix()
    r1 = vw.bootstrap_cllr(sources, matrix, n_boot=50, seed=0)
    r2 = vw.bootstrap_cllr(sources, matrix, n_boot=50, seed=0)
    assert (r1.lo, r1.hi, r1.n_used, r1.n_skipped) == (r2.lo, r2.hi, r2.n_used, r2.n_skipped)
    r3 = vw.bootstrap_cllr(sources, matrix, n_boot=50, seed=1)
    assert (r1.lo, r1.hi) != (r3.lo, r3.hi)


def test_bootstrap_skips_only_replicates_lacking_both_classes():
    """One slide with one scan: every replicate has zero pairs ⇒ all skipped."""
    res = vw.bootstrap_cllr(["A"], np.full((1, 1), np.nan), n_boot=20, seed=0)
    assert res.n_skipped == 20 and res.n_used == 0
    assert math.isnan(res.lo) and math.isnan(res.hi)


def test_bootstrap_unscored_pairs_are_excluded_not_imputed():
    sources, matrix = _toy_lr_matrix()
    matrix[0, 2] = matrix[2, 0] = np.nan  # a crashed pair has no LR anywhere
    res = vw.bootstrap_cllr(sources, matrix, n_boot=30, seed=0)
    assert res.n_used == 30 and np.isfinite([res.lo, res.hi]).all()


def test_lr_matrix_from_is_symmetric_with_nan_holes():
    matrix = vw.lr_matrix_from(3, [(0, 1), (1, 2)], np.array([4.0, 0.25]))
    assert matrix[0, 1] == matrix[1, 0] == 4.0
    assert matrix[1, 2] == matrix[2, 1] == 0.25
    assert np.isnan(matrix[0, 2]) and np.isnan(matrix[2, 0])


# --------------------------------------------------------------------------- #
# Calibration parity with the deployed report path
# --------------------------------------------------------------------------- #
def _synthetic_reference() -> LoadedReference:
    rng = np.random.default_rng(3)
    scores = np.concatenate([rng.normal(5.0, 1.0, 40), rng.normal(1.0, 1.0, 160)])
    labels = np.concatenate([np.ones(40), np.zeros(160)])
    return LoadedReference(path=Path("synthetic.npz"), scores=scores, labels=labels,
                           cluster_ids=np.array([], dtype="U"), provenance=None)


def test_calibrate_frozen_matches_deployed_report_lr():
    """The driver's single frozen fit must reproduce the LR (and bound-hit flag)
    that ``build_comparison_report`` — the deployed API path — reports."""
    ref = _synthetic_reference()
    probes = np.array([0.0, 2.5, 3.5, 9.0])
    lrs, hits, model = vw.calibrate_frozen(probes, ref)
    for probe, lr, hit in zip(probes, lrs, hits, strict=True):
        report = build_comparison_report(
            score=float(probe), reference_scores=ref.scores, reference_labels=ref.labels,
            domain="impressed", reference_name="synthetic", ci=False,
        )
        assert report.likelihood_ratio == pytest.approx(float(lr), rel=1e-9)
        assert report.lr_bound_hit == bool(hit)
        assert report.lr_bound_log10 == model._log_bound


def test_calibrate_frozen_caps_at_the_empirical_bound():
    ref = _synthetic_reference()  # minority class 40 ⇒ |log10 LR| ≤ log10(40)
    lrs, hits, model = vw.calibrate_frozen(np.array([50.0, -50.0]), ref)
    assert model._log_bound == pytest.approx(np.log10(40))
    assert hits.all()
    assert lrs[0] == pytest.approx(40.0) and lrs[1] == pytest.approx(1 / 40.0)


# --------------------------------------------------------------------------- #
# Verdict vocabulary (§1.3) and artifact shape
# --------------------------------------------------------------------------- #
def test_h1_verdict_uses_registered_vocabulary():
    assert vw.h1_verdict(0.45)["supported"]
    assert "transferred" in vw.h1_verdict(0.30)["label"]
    v = vw.h1_verdict(0.60)
    assert not v["supported"] and "remained informative" in v["label"]
    assert "failed to transfer" in vw.h1_verdict(1.2)["label"]


def test_not_evaluable_artifact_still_carries_counts_and_exclusions():
    records = [_record(i, "TW01") for i in range(3)]
    evaluable, _ = _screen(records)
    exclusions = (vw.Exclusion(vw.RULE_SCOPE_REFUSAL, "x", "refused"),)
    pairs, _ = vw.enumerate_pairs(records)
    ev = vw.check_evaluability(len(evaluable), 3)
    result = vw._not_evaluable(len(records), evaluable, exclusions, ev, len(pairs), 3)
    artifact = vw.result_to_artifact(result)
    assert artifact["verdict"] == "not evaluable as registered"
    assert artifact["metrics"] is None and artifact["h1"] is None
    assert artifact["counts"]["n_evaluable_scans"] == 3
    assert artifact["exclusions"]["by_rule"][vw.RULE_SCOPE_REFUSAL] == 1
    assert artifact["frozen"]["scorer_config_hash"] == vw.FROZEN_SCORER_CONFIG_HASH


def test_metrics_report_all_registered_secondaries():
    scores = np.array([9.0, 8.0, 1.0, 0.0, 2.0, 7.0])
    labels = np.array([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    lrs = np.array([30.0, 0.5, 0.2, 0.1, 4.0, 40.0])
    hits = np.array([True, False, False, False, False, True])
    m = vw.compute_metrics(scores, labels, lrs, hits)
    assert m["rmed"] == pytest.approx(0.5)  # one of two KM pairs has LR < 1
    assert m["rmep"] == pytest.approx(0.5)  # two of four KNM pairs have LR > 1
    assert m["frac_bound_limited"] == pytest.approx(2 / 6)
    assert m["calibration_loss"] == pytest.approx(m["pooled_cllr"] - m["cllr_min"])
    for key in ("pooled_cllr", "cllr_min", "auc_scores", "ece", "n_km", "n_knm"):
        assert key in m
