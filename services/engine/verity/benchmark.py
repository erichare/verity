"""The frozen, source-disjoint open benchmark — pairs, folds, hashes, and scoring.

A benchmark split is a *frozen contract*: a list of comparison pairs (each pair
identified by the SHA-256 content hashes of its two marks), a set of frozen
source-disjoint evaluation folds, and a ``split_hash`` over the whole thing. Two
parties holding the same ``split_hash`` are provably evaluating on the same pairs
under the same protocol — the replication-kit property the leaderboard rests on.

**The submission contract.** A submission is one likelihood ratio per pair. The
LR for a pair must be produced *without using the benchmark labels of any pair
involving either of its sources* (leave-the-pair's-sources-out). That is the
same discipline as the published source-disjoint validation; it cannot be
enforced mechanically on an honor-system leaderboard, but Verity's own reference
rows follow it exactly (:func:`loso_lrs`) and the kit documents it.

**Scoring.** Each frozen fold holds out a set of sources; the fold's test pairs
are those whose sources are *both* held out. A submission is scored per fold —
``Cllr`` (from the submitted LRs), ``Cllr_min`` (PAV floor on the LR ranks) and
``AUC`` — then summarized as mean ± sd, exactly mirroring
:func:`verity.decision.validation.barrel_disjoint_folds`. The headline number is
the **calibration loss** ``Cllr − Cllr_min``: how much of the reported weight of
evidence is miscalibrated — the axis the field does not otherwise score.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np

from .decision.lr import ScoreLRModel, cllr_min
from .decision.metrics import cllr, ece, roc_auc

PROTOCOL_VERSION = 1

#: Frozen protocol defaults — the same repeated source-disjoint splits (seed 0)
#: behind every published Verity number.
DEFAULT_N_SPLITS = 10
DEFAULT_TEST_FRAC = 0.4
DEFAULT_SEED = 0

# Fold-keeping rule, identical to ``barrel_disjoint_folds``: a candidate fold is
# kept only if the train side retains >= 3 same-source pairs and the test side
# holds >= 1.
_MIN_TRAIN_KM = 3
_MIN_TEST_KM = 1


def mark_hash(content_hashes: Sequence[str]) -> str:
    """A mark's identity hash. A single-scan mark *is* its scan's content hash
    (so the mark can be looked up in the catalog directly); a multi-scan mark
    (e.g. a bullet = its land scans) hashes the sorted scan hashes."""
    hashes = sorted(content_hashes)
    if not hashes:
        raise ValueError("mark_hash needs at least one scan content hash")
    if len(hashes) == 1:
        return hashes[0]
    return hashlib.sha256("\n".join(hashes).encode()).hexdigest()


def pair_id(hash_a: str, hash_b: str) -> str:
    """Order-independent pair identifier: SHA-256 over the sorted mark hashes.
    Built from *content* hashes (never catalog row ids), so it is portable —
    anyone holding the underlying scans can recompute it."""
    return hashlib.sha256("\n".join(sorted((hash_a, hash_b))).encode()).hexdigest()


@dataclass(frozen=True)
class BenchmarkPair:
    """One frozen comparison: two marks (by content hash), the ground-truth
    label (1 = same source) and the per-side source ids."""

    pair_id: str
    hash_a: str
    hash_b: str
    label: int
    source_a: str
    source_b: str


def make_pair(
    hash_a: str, hash_b: str, label: int, source_a: str, source_b: str
) -> BenchmarkPair:
    """Build a :class:`BenchmarkPair` in canonical (sorted-hash) order, keeping
    each source attached to its mark."""
    if hash_b < hash_a:
        hash_a, hash_b = hash_b, hash_a
        source_a, source_b = source_b, source_a
    return BenchmarkPair(
        pair_id=pair_id(hash_a, hash_b),
        hash_a=hash_a,
        hash_b=hash_b,
        label=int(label),
        source_a=source_a,
        source_b=source_b,
    )


@dataclass(frozen=True)
class FrozenFold:
    """One evaluation fold: the held-out source set and the indices (into the
    split's pair list) of the pairs whose sources are both held out."""

    index: int
    test_sources: tuple[str, ...]
    pair_indices: tuple[int, ...]


@dataclass(frozen=True)
class FrozenSplit:
    """A frozen benchmark split: pairs + folds + the protocol that produced them.
    ``split_hash`` commits to all of it."""

    name: str
    pairs: tuple[BenchmarkPair, ...]
    folds: tuple[FrozenFold, ...]
    protocol: dict = field(default_factory=dict)

    @property
    def split_hash(self) -> str:
        return split_hash(self.pairs, self.folds)


def freeze_folds(
    pairs: Sequence[BenchmarkPair],
    *,
    n_splits: int = DEFAULT_N_SPLITS,
    test_frac: float = DEFAULT_TEST_FRAC,
    seed: int = DEFAULT_SEED,
) -> tuple[FrozenFold, ...]:
    """Freeze the repeated source-disjoint splits over a pair list.

    The RNG discipline is identical to
    :func:`verity.decision.validation.barrel_disjoint_folds`: one
    ``default_rng(seed)``, and per candidate split a permutation of the sorted
    source list with the first ``round(n * test_frac)`` sources held out. A
    candidate is kept under the same rule (train keeps >= 3 same-source pairs,
    test holds >= 1), evaluated on the pair *labels* only — so the frozen folds
    do not depend on anyone's scores."""
    sources = sorted({p.source_a for p in pairs} | {p.source_b for p in pairs})
    labels = np.array([p.label for p in pairs])
    rng = np.random.default_rng(seed)
    n_test = max(2, round(len(sources) * test_frac))
    folds: list[FrozenFold] = []
    for _ in range(n_splits):
        test = set(rng.permutation(sources)[:n_test].tolist())
        in_test = np.array([p.source_a in test and p.source_b in test for p in pairs])
        in_train = np.array(
            [p.source_a not in test and p.source_b not in test for p in pairs]
        )
        if labels[in_train].sum() < _MIN_TRAIN_KM or labels[in_test].sum() < _MIN_TEST_KM:
            continue
        folds.append(
            FrozenFold(
                index=len(folds),
                test_sources=tuple(sorted(test)),
                pair_indices=tuple(int(i) for i in np.flatnonzero(in_test)),
            )
        )
    return tuple(folds)


def split_hash(pairs: Sequence[BenchmarkPair], folds: Sequence[FrozenFold]) -> str:
    """SHA-256 over the canonical split serialization: one sorted line per pair
    — ``pair_id,hash_a,hash_b,label,<fold indices>`` — where the fold list is
    every fold in which the pair is a *test* pair. Hash equality ⇒ identical
    pairs, labels, and fold structure."""
    membership: dict[int, list[int]] = {}
    for fold in folds:
        for idx in fold.pair_indices:
            membership.setdefault(idx, []).append(fold.index)
    lines = []
    for i, p in enumerate(pairs):
        in_folds = ";".join(str(f) for f in sorted(membership.get(i, [])))
        lines.append(f"{p.pair_id},{p.hash_a},{p.hash_b},{p.label},{in_folds}")
    return hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()


def loso_lrs(
    scores: np.ndarray,
    pairs: Sequence[BenchmarkPair],
    *,
    lr_bound: str | float | None = "auto",
) -> np.ndarray:
    """Leave-the-pair's-sources-out calibrated LRs — Verity's reference
    submission, and the calibration discipline the contract asks of everyone.

    For each distinct source pair ``{a, b}``, a fresh :class:`ScoreLRModel` is
    fit on every pair involving *neither* source, then applied to that group's
    pairs. Every emitted LR is therefore calibrated source-disjointly from the
    pair it scores. Groups whose exclusion starves the train side of same-source
    pairs get ``NaN`` (cannot honestly calibrate)."""
    scores = np.asarray(scores, dtype=np.float64)
    if len(scores) != len(pairs):
        raise ValueError(f"{len(scores)} scores for {len(pairs)} pairs")
    labels = np.array([p.label for p in pairs], dtype=np.float64)
    src_a = np.array([p.source_a for p in pairs])
    src_b = np.array([p.source_b for p in pairs])

    out = np.full(len(scores), np.nan)
    groups: dict[frozenset, list[int]] = {}
    for i, p in enumerate(pairs):
        groups.setdefault(frozenset((p.source_a, p.source_b)), []).append(i)
    for excluded, indices in groups.items():
        train = ~(np.isin(src_a, list(excluded)) | np.isin(src_b, list(excluded)))
        if labels[train].sum() < _MIN_TRAIN_KM or (labels[train] == 0).sum() < _MIN_TRAIN_KM:
            continue
        model = ScoreLRModel(lr_bound=lr_bound).fit(scores[train], labels[train])
        idx = np.array(indices)
        out[idx] = model.predict_lr(scores[idx])
    return out


def validate_submission_lrs(lrs: np.ndarray) -> list[str]:
    """The junk-LR guard, benchmark edition: every submitted value must be a
    finite, strictly positive likelihood ratio. Returns human-readable problems
    (empty = valid)."""
    lrs = np.asarray(lrs, dtype=np.float64)
    problems = []
    n_bad = int((~np.isfinite(lrs)).sum())
    if n_bad:
        problems.append(f"{n_bad} non-finite LR(s) — every pair needs a finite LR")
    n_neg = int((np.isfinite(lrs) & (lrs <= 0.0)).sum())
    if n_neg:
        problems.append(f"{n_neg} LR(s) <= 0 — a likelihood ratio is strictly positive")
    return problems


def score_submission(
    lrs: np.ndarray,
    pairs: Sequence[BenchmarkPair],
    folds: Iterable[FrozenFold],
) -> dict:
    """Score one-LR-per-pair against the frozen folds.

    Per fold (its test pairs only): ``Cllr`` from the submitted LRs, ``Cllr_min``
    (PAV floor, using ``log10 LR`` as the score) and ``AUC``. Summary = mean ± sd
    across folds plus the pooled (all-pair) metrics and the headline
    ``calibration_loss``."""
    lrs = np.asarray(lrs, dtype=np.float64)
    if len(lrs) != len(pairs):
        raise ValueError(f"{len(lrs)} LRs for {len(pairs)} pairs")
    problems = validate_submission_lrs(lrs)
    if problems:
        raise ValueError("; ".join(problems))
    labels = np.array([p.label for p in pairs], dtype=np.float64)
    log_lr = np.log10(lrs)

    rows = []
    for fold in folds:
        idx = np.array(fold.pair_indices)
        lf, yf = lrs[idx], labels[idx]
        if yf.sum() < 1 or (yf == 0).sum() < 1:
            continue
        rows.append(
            {
                "fold": fold.index,
                "n_pairs": int(len(idx)),
                "cllr": cllr(lf[yf == 1], lf[yf == 0]),
                "cllr_min": cllr_min(log_lr[idx], yf),
                "auc": roc_auc(log_lr[idx], yf),
            }
        )
    if not rows:
        raise ValueError("no scorable folds (every fold lacked a KM or KNM test pair)")

    c = np.array([r["cllr"] for r in rows])
    cm = np.array([r["cllr_min"] for r in rows])
    au = np.array([r["auc"] for r in rows])
    return {
        "protocol_version": PROTOCOL_VERSION,
        "n_folds": len(rows),
        "cllr": float(c.mean()),
        "cllr_std": float(c.std()),
        "cllr_min": float(cm.mean()),
        "cllr_min_std": float(cm.std()),
        "auc": float(au.mean()),
        "auc_std": float(au.std()),
        "calibration_loss": float(c.mean() - cm.mean()),
        "pooled": {
            "n_pairs": int(len(pairs)),
            "n_km": int(labels.sum()),
            "n_knm": int((labels == 0).sum()),
            "cllr": cllr(lrs[labels == 1], lrs[labels == 0]),
            "cllr_min": cllr_min(log_lr, labels),
            "auc": roc_auc(log_lr, labels),
            "ece": ece(lrs[labels == 1], lrs[labels == 0]),
        },
        "folds": rows,
    }
