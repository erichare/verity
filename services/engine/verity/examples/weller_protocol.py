"""The registered Weller protocol, as pure machinery (docs/weller-preregistration.md).

Everything mechanical in the registered analysis lives here so it can be unit
tested on synthetic data with zero network and zero Weller access: the §5.5
exclusion rules, §4 pair enumeration/labeling, the §5.5 evaluability floor, the
frozen scoring path (identical to ``build_cartridge_fadul_reference``), the
deployed calibration idiom (``verity/report.py``), the §5.1/§5.2 metrics, and
the §5.2 cluster bootstrap on the frozen LRs. The one-shot driver
(``validate_weller_frozen``) wires these to the catalog and the committed
artifacts; nothing here reads data or writes files on its own.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

from verity.benchmark import BenchmarkPair, make_pair
from verity.cmr import areal_votes, consensus_members
from verity.decision import DEFAULT_SCORER_CONFIG, check_applicability
from verity.decision.lr import ScoreLRModel, cllr_min
from verity.decision.metrics import cllr, ece, roc_auc
from verity.decision.scope_guard import ScopeReport
from verity.surface import Surface

from ._reference_io import LoadedReference

# ---- Registered study constants (§3, §5) ------------------------------------ #
N_REGISTERED_SCANS = 95  # public metadata: 95 X3P files under TW01..TW11
CLLR_H1_THRESHOLD = 0.45  # §5.1 decision rule, on the pooled point estimate
MIN_SCAN_FRACTION = 0.5  # §5.5 evaluability floor: >= 50% of the 95 scans
MIN_KM_PAIRS = 30  # §5.5 evaluability floor: >= 30 same-source pairs
BOOTSTRAP_B = 2000  # §5.2 cluster bootstrap
BOOTSTRAP_SEED = 0

# §5.5 exclusion rules, in registered order. A scan failing several is counted
# under the first triggered rule.
RULE_UNPARSEABLE = "unparseable"
RULE_UNATTRIBUTABLE = "unattributable"
RULE_DUPLICATE = "duplicate"
RULE_SCOPE_REFUSAL = "scope_refusal"
RULE_PAIR_CRASH = "pair_crash"  # §5.6: pipeline crash on a specific pair
ALL_RULES = (RULE_UNPARSEABLE, RULE_UNATTRIBUTABLE, RULE_DUPLICATE, RULE_SCOPE_REFUSAL,
             RULE_PAIR_CRASH)

# Mirrors the deployed API's comparison-path guard (services/api/verity_api/main.py):
# only the hard, unrecoverable failures block; coverage/signal stay warnings.
_HARD_REFUSE_CHECKS = frozenset({"resolution", "modality"})

_CFG = DEFAULT_SCORER_CONFIG


# --------------------------------------------------------------------------- #
# Data records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ScanRecord:
    """One candidate scan: its source (TW slide directory; ``None`` if the catalog
    cannot attribute it), a human name, and its content hash."""

    source: str | None
    name: str
    content_hash: str


@dataclass(frozen=True)
class Exclusion:
    """One §5.5/§5.6 exclusion: the mechanical rule, the item (scan name or pair
    id) and the recorded reason."""

    rule: str
    item: str
    reason: str


@dataclass(frozen=True)
class EvaluableScan:
    """A scan that survived every §5.5 rule, with its precomputed areal signature."""

    record: ScanRecord
    signature: np.ndarray


def _surface_from_bytes(data: bytes) -> Surface:
    """Decode X3P bytes with the committed parser (verifies the embedded MD5) —
    the same decode the deployed API applies to uploads."""
    import verity_x3p

    fd, path = tempfile.mkstemp(suffix=".x3p")
    os.close(fd)
    try:
        Path(path).write_bytes(data)
        s = verity_x3p.read_x3p(path)
        return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x,
                       dy=s.increment_y)
    finally:
        Path(path).unlink(missing_ok=True)


def deployed_scope_check(surface: Surface) -> ScopeReport:
    """The per-scan applicability guard exactly as the hosted API applies it on the
    impressed comparison path — refuse mode, blocking only resolution/modality; a
    scan whose scope cannot even be evaluated is refused, never admitted."""
    try:
        return check_applicability(
            surface, domain="impressed", mode="refuse", blocking=_HARD_REFUSE_CHECKS
        )
    except Exception as exc:  # noqa: BLE001 - cannot establish scope => refuse, not admit
        return ScopeReport(
            admissible=False,
            mode="refuse",
            domain="impressed",
            checks=[],
            overall_reason=f"could not evaluate applicability of this scan: {exc}",
        )


def _areal_signature(surface: Surface) -> np.ndarray:
    from verity.areal import areal_signature

    return areal_signature(surface)


# --------------------------------------------------------------------------- #
# §5.5 — mechanical exclusions
# --------------------------------------------------------------------------- #
def screen_scans(
    records: Sequence[ScanRecord],
    *,
    get_bytes: Callable[[ScanRecord], bytes],
    read_surface: Callable[[bytes], Surface],
    scope_check: Callable[[Surface], ScopeReport],
    make_signature: Callable[[Surface], np.ndarray],
) -> tuple[tuple[EvaluableScan, ...], tuple[Exclusion, ...]]:
    """Apply the §5.5 rules in registered order (1 unparseable, 2 unattributable,
    3 duplicate, 4 scope refusal) to ``records`` (already in deterministic order —
    dedup keeps the FIRST occurrence). Label-blind and score-blind by construction.

    A content hash appearing under more than one TW directory is unattributable
    (rule 2: not assignable to exactly one source); a repeat of an already-seen
    hash under the same source is a duplicate (rule 3). A crash computing the
    committed signature is rule-1 semantics per §5.6 (counted, reported, excluded).
    """
    sources_of: dict[str, set[str]] = {}
    for r in records:
        if r.source is not None:
            sources_of.setdefault(r.content_hash, set()).add(r.source)

    kept: list[EvaluableScan] = []
    excluded: list[Exclusion] = []
    seen_hashes: set[str] = set()
    for r in records:
        try:  # rule 1 — committed parser / integrity checks
            surface = read_surface(get_bytes(r))
        except Exception as exc:  # noqa: BLE001 - the failure IS the recorded outcome
            excluded.append(Exclusion(RULE_UNPARSEABLE, r.name, f"parse failed: {exc}"))
            continue
        if r.source is None or len(sources_of.get(r.content_hash, set())) != 1:  # rule 2
            n_dirs = len(sources_of.get(r.content_hash, set()))
            reason = ("no source directory recorded" if r.source is None
                      else f"content appears under {n_dirs} slide directories")
            excluded.append(Exclusion(RULE_UNATTRIBUTABLE, r.name, reason))
            continue
        if r.content_hash in seen_hashes:  # rule 3 — first occurrence kept
            excluded.append(
                Exclusion(RULE_DUPLICATE, r.name,
                          f"content hash {r.content_hash[:12]}… already included")
            )
            continue
        seen_hashes.add(r.content_hash)
        report = scope_check(surface)  # rule 4 — deployed guard, per scan
        if not report.admissible:
            excluded.append(Exclusion(RULE_SCOPE_REFUSAL, r.name, report.overall_reason))
            continue
        try:
            signature = make_signature(surface)
        except Exception as exc:  # noqa: BLE001 - §5.6: counted under rule-1 semantics
            excluded.append(
                Exclusion(RULE_UNPARSEABLE, r.name, f"pipeline crash computing signature: {exc}")
            )
            continue
        kept.append(EvaluableScan(record=r, signature=signature))
    return tuple(kept), tuple(excluded)


# --------------------------------------------------------------------------- #
# §4 — pair enumeration and labeling
# --------------------------------------------------------------------------- #
def enumerate_pairs(
    records: Sequence[ScanRecord],
) -> tuple[tuple[BenchmarkPair, ...], tuple[tuple[int, int], ...]]:
    """All unordered pairs of distinct evaluable scans (``itertools.combinations``,
    the committed benchmark builder's enumeration rule). KM iff same TW directory.
    Returns the pairs plus each pair's (i, j) indices into ``records``."""
    pairs: list[BenchmarkPair] = []
    idx: list[tuple[int, int]] = []
    for (i, a), (j, b) in combinations(enumerate(records), 2):
        pairs.append(
            make_pair(a.content_hash, b.content_hash,
                      1 if a.source == b.source else 0, str(a.source), str(b.source))
        )
        idx.append((i, j))
    return tuple(pairs), tuple(idx)


def score_pair(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    """The DEPLOYED impressed score — identical to ``build_cartridge_fadul_reference``:
    count of congruent matching regions (CMR-2D) under the frozen scorer config."""
    members = consensus_members(
        areal_votes(sig_a, sig_b), corr_thresh=_CFG.cmr_corr, transform_tol=_CFG.cmr_tol
    )
    return float(len(members))


# Per-worker signature table, populated once per process by the pool initializer
# (§0 frozen scorer): workers reference scans by index instead of re-pickling the
# ~95 signature arrays for every one of the thousands of pairs.
_WORKER_SIGS: list[np.ndarray] | None = None


def _init_scoring(signatures: list[np.ndarray]) -> None:
    global _WORKER_SIGS
    _WORKER_SIGS = signatures


def _score_ij(ij: tuple[int, int]) -> tuple[float, str | None]:
    """Worker: the identical frozen ``score_pair`` on two precomputed signatures.
    A per-pair exception is returned (not raised) so §5.6 handling is unchanged."""
    i, j = ij
    assert _WORKER_SIGS is not None
    try:
        return score_pair(_WORKER_SIGS[i], _WORKER_SIGS[j]), None
    except Exception as exc:  # noqa: BLE001 - §5.6: counted, reported, excluded upstream
        return float("nan"), f"pipeline crash: {exc}"


def _progress(done: int, total: int, *, every: int = 250) -> None:
    if total and (done % every == 0 or done == total):
        print(f"  scored {done}/{total} pairs", flush=True)


def score_pairs(
    evaluable: Sequence[EvaluableScan],
    pairs: Sequence[BenchmarkPair],
    idx: Sequence[tuple[int, int]],
    *,
    score_fn: Callable[[np.ndarray, np.ndarray], float] = score_pair,
    workers: int = 1,
) -> tuple[np.ndarray, tuple[Exclusion, ...]]:
    """Score every enumerated pair once. A per-pair crash yields ``NaN`` plus a
    counted §5.6 exclusion — the pair is never retried differently.

    ``workers <= 1`` runs the serial path (and honors an injected ``score_fn``,
    used by the synthetic unit tests). ``workers > 1`` fans the *independent*
    per-pair scoring across processes using the module-level frozen ``score_pair``;
    ``ProcessPoolExecutor.map`` preserves input order, so ``scores[k]`` still aligns
    with ``pairs[k]`` and the result is bit-identical to the serial path (validated
    by the Fadul self-check, which runs through this same function)."""
    n = len(pairs)
    scores = np.full(n, np.nan)
    excluded: list[Exclusion] = []
    if workers <= 1 or n == 0:
        for k, (p, (i, j)) in enumerate(zip(pairs, idx, strict=True)):
            try:
                scores[k] = score_fn(evaluable[i].signature, evaluable[j].signature)
            except Exception as exc:  # noqa: BLE001 - §5.6: counted, reported, excluded
                excluded.append(Exclusion(RULE_PAIR_CRASH, p.pair_id, f"pipeline crash: {exc}"))
            _progress(k + 1, n)
        return scores, tuple(excluded)

    from concurrent.futures import ProcessPoolExecutor

    signatures = [e.signature for e in evaluable]
    with ProcessPoolExecutor(
        max_workers=workers, initializer=_init_scoring, initargs=(signatures,)
    ) as pool:
        for k, (value, err) in enumerate(pool.map(_score_ij, idx, chunksize=16)):
            if err is None:
                scores[k] = value
            else:
                excluded.append(Exclusion(RULE_PAIR_CRASH, pairs[k].pair_id, err))
            _progress(k + 1, n)
    return scores, tuple(excluded)


# --------------------------------------------------------------------------- #
# §5.5 — evaluability floor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Evaluability:
    evaluable: bool
    reasons: tuple[str, ...]


def check_evaluability(
    n_evaluable_scans: int,
    n_km_pairs: int,
    *,
    n_registered: int = N_REGISTERED_SCANS,
    min_scan_fraction: float = MIN_SCAN_FRACTION,
    min_km_pairs: int = MIN_KM_PAIRS,
) -> Evaluability:
    """The registered floor: fewer than 50% of the 95 scans or fewer than 30
    same-source pairs ⇒ 'not evaluable as registered' (§5.5)."""
    reasons = []
    if n_evaluable_scans < n_registered * min_scan_fraction:
        reasons.append(
            f"{n_evaluable_scans} evaluable scans < {min_scan_fraction:.0%} of the "
            f"{n_registered} registered scans"
        )
    if n_km_pairs < min_km_pairs:
        reasons.append(f"{n_km_pairs} same-source pairs < the registered floor of "
                       f"{min_km_pairs}")
    return Evaluability(evaluable=not reasons, reasons=tuple(reasons))


# --------------------------------------------------------------------------- #
# Frozen calibration (the exact deployed idiom — verity/report.py)
# --------------------------------------------------------------------------- #
def calibrate_frozen(
    scores: np.ndarray, reference: LoadedReference
) -> tuple[np.ndarray, np.ndarray, ScoreLRModel]:
    """Fit ``ScoreLRModel(lr_bound="auto")`` ONCE on the frozen reference and map
    the Weller scores to capped LRs with bound-hit flags — byte-identical behavior
    to ``build_comparison_report`` (verity/report.py). Nothing is refit."""
    model = ScoreLRModel(lr_bound="auto").fit(reference.scores, reference.labels)
    lrs, bound_hits = model.predict_lr(
        np.asarray(scores, dtype=np.float64), return_bound_hit=True
    )
    return lrs, bound_hits, model


# --------------------------------------------------------------------------- #
# §5.1 + §5.2 — metrics
# --------------------------------------------------------------------------- #
def compute_metrics(
    scores: np.ndarray, labels: np.ndarray, lrs: np.ndarray, bound_hits: np.ndarray
) -> dict:
    """Primary pooled Cllr plus every registered secondary, all from the committed
    implementations (``verity.decision.metrics`` / ``verity.decision.lr``)."""
    km, knm = labels == 1, labels == 0
    pooled = cllr(lrs[km], lrs[knm])
    floor = cllr_min(scores, labels)  # PAV floor on the CMR scores (does the score transfer?)
    return {
        "pooled_cllr": float(pooled),
        "cllr_min": float(floor),
        "calibration_loss": float(pooled - floor),
        "auc_scores": float(roc_auc(scores, labels)),
        "ece": float(ece(lrs[km], lrs[knm])),
        "rmed": float((lrs[km] < 1.0).mean()),  # KM pairs reported as exculpatory
        "rmep": float((lrs[knm] > 1.0).mean()),  # KNM pairs reported as inculpatory
        "frac_bound_limited": float(bound_hits.mean()),
        "n_km": int(km.sum()),
        "n_knm": int(knm.sum()),
    }


# --------------------------------------------------------------------------- #
# §5.2 — cluster bootstrap over slides, on the FROZEN LRs
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BootstrapCllr:
    lo: float
    hi: float
    n_boot: int
    seed: int
    n_used: int
    n_skipped: int


def replicate_pairs(
    draw: Sequence[str], scans_by_slide: Mapping[str, Sequence[int]]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Enumerate one bootstrap replicate's pairs under the §4.2 rules: concatenate
    the scans of every drawn slide copy, take all unordered position pairs, drop
    self-pairs (a scan never pairs with itself), and label KM by slide equality —
    so pairs between two copies of the SAME resampled slide are within-source.
    Returns ``(scan_i, scan_j, is_km)`` index/label arrays."""
    idx: list[int] = []
    src: list[str] = []
    for slide in draw:
        scans = scans_by_slide[slide]
        idx.extend(scans)
        src.extend([slide] * len(scans))
    if len(idx) < 2:
        empty = np.array([], dtype=int)
        return empty, empty.copy(), np.array([], dtype=bool)
    idx_arr, src_arr = np.asarray(idx, dtype=int), np.asarray(src)
    iu, ju = np.triu_indices(len(idx_arr), k=1)
    a, b = idx_arr[iu], idx_arr[ju]
    keep = a != b  # self-pair exclusion
    return a[keep], b[keep], (src_arr[iu] == src_arr[ju])[keep]


def bootstrap_cllr(
    scan_sources: Sequence[str],
    lr_matrix: np.ndarray,
    *,
    n_boot: int = BOOTSTRAP_B,
    seed: int = BOOTSTRAP_SEED,
) -> BootstrapCllr:
    """Resample the slides with replacement (B replicates, ``default_rng(seed)``);
    per replicate re-enumerate pairs via :func:`replicate_pairs`, look up each
    pair's FROZEN LR from the original run (``NaN`` = pair not scored ⇒ excluded,
    consistent with §5.6), recompute pooled Cllr, and report the 2.5th/97.5th
    percentiles. A replicate is skipped only if it lacks both classes (no pairs)."""
    slides = sorted(set(scan_sources))
    scans_by_slide = {
        s: [i for i, src in enumerate(scan_sources) if src == s] for s in slides
    }
    rng = np.random.default_rng(seed)
    values: list[float] = []
    n_skipped = 0
    for _ in range(n_boot):
        draw = [slides[k] for k in rng.integers(0, len(slides), size=len(slides))]
        a, b, km = replicate_pairs(draw, scans_by_slide)
        lr = lr_matrix[a, b] if a.size else np.array([])
        scored = np.isfinite(lr)
        lr, km = lr[scored], km[scored]
        if lr.size == 0:  # lacks both classes — nothing to pool
            n_skipped += 1
            continue
        values.append(cllr(lr[km], lr[~km]))
    if values:
        lo, hi = np.percentile(np.asarray(values), [2.5, 97.5])
    else:
        lo = hi = float("nan")
    return BootstrapCllr(lo=float(lo), hi=float(hi), n_boot=n_boot, seed=seed,
                         n_used=len(values), n_skipped=n_skipped)


def lr_matrix_from(
    n_scans: int, idx: Sequence[tuple[int, int]], lrs_by_pair: np.ndarray
) -> np.ndarray:
    """Symmetric scan×scan LR lookup for the bootstrap. ``NaN`` where no LR exists
    (crashed pair). ``lrs_by_pair`` aligns positionally with ``idx``."""
    matrix = np.full((n_scans, n_scans), np.nan)
    for (i, j), lr in zip(idx, lrs_by_pair, strict=True):
        matrix[i, j] = matrix[j, i] = lr
    return matrix


# --------------------------------------------------------------------------- #
# §1.3 — pre-registered interpretation vocabulary
# --------------------------------------------------------------------------- #
def h1_verdict(pooled_cllr: float) -> dict:
    if pooled_cllr <= CLLR_H1_THRESHOLD:
        label = ("the frozen pipeline transferred to an independent study at near "
                 "within-study performance")
    elif pooled_cllr < 1.0:
        label = ("the frozen pipeline remained informative on an independent study "
                 "but degraded beyond the registered threshold")
    else:
        label = "the frozen pipeline failed to transfer (uninformative or miscalibrated)"
    return {
        "threshold": CLLR_H1_THRESHOLD,
        "pooled_cllr": float(pooled_cllr),
        "supported": bool(pooled_cllr <= CLLR_H1_THRESHOLD),
        "label": label,
    }


# --------------------------------------------------------------------------- #
# The full registered pipeline over a set of scan records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProtocolResult:
    """Everything the registered run produces, before artifact writing."""

    n_records: int
    evaluable: tuple[EvaluableScan, ...]
    exclusions: tuple[Exclusion, ...]
    evaluability: Evaluability
    pairs: tuple[BenchmarkPair, ...]  # scored pairs only (crashes excluded + counted)
    scores: np.ndarray
    labels: np.ndarray
    lrs: np.ndarray
    bound_hits: np.ndarray
    lr_bound_log10: float | None
    metrics: dict | None
    bootstrap: BootstrapCllr | None
    n_pairs_enumerated: int
    n_km_enumerated: int


def _not_evaluable(
    n_records: int, evaluable: tuple, exclusions: tuple, ev: Evaluability,
    n_pairs: int, n_km: int,
) -> ProtocolResult:
    empty = np.array([])
    return ProtocolResult(
        n_records=n_records, evaluable=evaluable, exclusions=exclusions, evaluability=ev,
        pairs=(), scores=empty, labels=empty, lrs=empty, bound_hits=empty,
        lr_bound_log10=None, metrics=None, bootstrap=None,
        n_pairs_enumerated=n_pairs, n_km_enumerated=n_km,
    )


def run_protocol(
    records: Sequence[ScanRecord],
    get_bytes: Callable[[ScanRecord], bytes],
    *,
    reference: LoadedReference,
    n_registered: int = N_REGISTERED_SCANS,
    min_km_pairs: int = MIN_KM_PAIRS,
    n_boot: int = BOOTSTRAP_B,
    seed: int = BOOTSTRAP_SEED,
    workers: int = 1,
) -> ProtocolResult:
    """§5.1/§5.2 end to end: screen → enumerate → floor → score → calibrate →
    metrics → bootstrap. Pure with respect to its inputs; writes nothing.

    ``workers`` only fans the independent per-pair scoring across processes; every
    score, label, LR, and metric is identical to a serial run (§2.2: no analysis
    parameter changes — this is execution scheduling, not a scorer knob)."""
    ordered = sorted(records, key=lambda r: (r.source or "", r.name))
    evaluable, exclusions = screen_scans(
        ordered, get_bytes=get_bytes, read_surface=_surface_from_bytes,
        scope_check=deployed_scope_check, make_signature=_areal_signature,
    )
    pairs, idx = enumerate_pairs([s.record for s in evaluable])
    n_km_enum = sum(p.label for p in pairs)
    ev = check_evaluability(len(evaluable), n_km_enum,
                            n_registered=n_registered, min_km_pairs=min_km_pairs)
    if not ev.evaluable:
        return _not_evaluable(len(records), evaluable, exclusions, ev, len(pairs), n_km_enum)

    print(f"scoring {len(pairs)} pairs through the frozen CMR-2D path "
          f"({workers} worker{'s' if workers != 1 else ''}) ...", flush=True)
    raw_scores, crash_exclusions = score_pairs(evaluable, pairs, idx, workers=workers)
    exclusions = exclusions + crash_exclusions
    scored = np.isfinite(raw_scores)
    kept_pairs = tuple(p for p, ok in zip(pairs, scored, strict=True) if ok)
    kept_idx = tuple(ij for ij, ok in zip(idx, scored, strict=True) if ok)
    scores = raw_scores[scored]
    labels = np.array([p.label for p in kept_pairs], dtype=np.float64)

    # Crashed KM pairs are "excluded under rule 1/4 semantics" (§5.6) — re-check
    # the same-source floor on what actually remains scorable.
    ev = check_evaluability(len(evaluable), int(labels.sum()),
                            n_registered=n_registered, min_km_pairs=min_km_pairs)
    if not ev.evaluable:
        return _not_evaluable(len(records), evaluable, exclusions, ev, len(pairs), n_km_enum)

    lrs, bound_hits, model = calibrate_frozen(scores, reference)
    metrics = compute_metrics(scores, labels, lrs, bound_hits)
    matrix = lr_matrix_from(len(evaluable), kept_idx, lrs)
    print(f"pooled Cllr {metrics['pooled_cllr']:.4f}; running {n_boot}-replicate "
          f"slide bootstrap ...", flush=True)
    boot = bootstrap_cllr([str(s.record.source) for s in evaluable], matrix,
                          n_boot=n_boot, seed=seed)
    return ProtocolResult(
        n_records=len(records), evaluable=evaluable, exclusions=exclusions, evaluability=ev,
        pairs=kept_pairs, scores=scores, labels=labels, lrs=lrs, bound_hits=bound_hits,
        lr_bound_log10=model._log_bound,  # the deployed cap, as report.py surfaces it
        metrics=metrics, bootstrap=boot,
        n_pairs_enumerated=len(pairs), n_km_enumerated=n_km_enum,
    )
