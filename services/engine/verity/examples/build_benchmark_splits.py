"""Freeze the open-benchmark splits — pairs, folds, split hashes, and Verity's
own reference submissions — for all three validated modalities.

The frozen pairs reuse the *committed* calibration references
(``services/api/verity_api/references/*.npz``) as the score source: this builder
re-enumerates each reference's pairs with the same code path and attaches mark
identities (catalog content hashes), then asserts the labels and source clusters
align positionally with the shipped ``.npz`` before adopting its scores. The
benchmark therefore stays in cryptographic lockstep with the deployed references
— if they drift, this builder refuses to run (regenerate the references first
with ``verity-build-references --write``).

Per split it writes (default ``services/catalog/benchmarks/<name>/``):

* ``pairs.csv.gz``       — pair_id, mark hashes, label, sources, fold membership
* ``marks.csv.gz``       — mark hash → source + constituent scan content hashes
* ``folds.json``         — each frozen fold's held-out source set
* ``provenance.json``    — protocol, ``split_hash``, counts, scorer config, datasets
* ``verity_submission.csv.gz`` — Verity's leave-sources-out calibrated LRs
* ``verity_metrics.json``      — that submission scored under the frozen protocol

Needs the local catalog (bullets) plus the cartridge/tmaRks caches; no network.

    cd services/engine && uv run verity-build-benchmark [--out DIR] [--only NAME]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np

from verity.benchmark import (
    DEFAULT_N_SPLITS,
    DEFAULT_SEED,
    DEFAULT_TEST_FRAC,
    PROTOCOL_VERSION,
    BenchmarkPair,
    FrozenFold,
    freeze_folds,
    loso_lrs,
    make_pair,
    mark_hash,
    score_submission,
    split_hash,
)
from verity.decision import DEFAULT_SCORER_CONFIG

from ._reference_io import git_short_hash, load_reference
from .build_bullet_pooled_reference import _BULLET_STUDIES, _catalog_dir

_ROOT = Path(__file__).resolve().parents[4]
_REF_DIR = _ROOT / "services/api/verity_api/references"
_DEFAULT_OUT = _ROOT / "services/catalog/benchmarks"

#: The submission contract, stated once and embedded in every provenance file.
CONTRACT = (
    "One likelihood ratio per pair. The LR for a pair must be produced without "
    "using the benchmark labels of any pair involving either of its sources "
    "(leave-the-pair's-sources-out) — the same source-disjoint discipline the "
    "frozen folds score."
)


@dataclass(frozen=True)
class Mark:
    """One benchmark mark: its identity hash, public source id, a human label,
    and the constituent scan content hashes."""

    hash: str
    source: str
    label: str
    scan_hashes: tuple[str, ...]


@dataclass(frozen=True)
class SplitInputs:
    """Everything a modality contributes: marks, enumerated pairs (in reference
    ``.npz`` order), the npz-style cluster key per pair (for alignment), and
    dataset descriptors."""

    name: str
    title: str
    modality: str
    score_kind: str
    reference_npz: str
    marks: tuple[Mark, ...]
    pairs: tuple[BenchmarkPair, ...]
    npz_clusters: tuple[str, ...]
    datasets: list[dict]


# --------------------------------------------------------------------------- #
# Bullets — multi-scan marks from the catalog, in build_bullet_pooled order.
# --------------------------------------------------------------------------- #
def _bullet_inputs() -> SplitInputs:
    """Re-enumerate ``build_bullet_pooled_reference``'s pairs with content hashes
    attached. Iteration order (studies → firearms → bullets → lands) is kept
    identical so positions align with the committed ``bullet_pooled.npz``."""
    import verity_catalog.models as m
    from sqlmodel import Session, create_engine, select

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    by_barrel: dict[str, list[tuple[str, Mark]]] = {}
    npz_src: dict[str, str] = {}  # public source id -> npz cluster source id
    with Session(engine) as session:
        for ext, tag in _BULLET_STUDIES.items():
            study = session.exec(select(m.Study).where(m.Study.external_id == ext)).first()
            if study is None:
                raise SystemExit(f"bullet study {ext} ({tag}) not in the local catalog")
            firearms = session.exec(select(m.Firearm).where(m.Firearm.study_id == study.id)).all()
            for fa in firearms:
                source = f"{ext}:{fa.external_id}"
                npz_src[source] = f"{study.id}:{fa.external_id}"
                bullets = session.exec(select(m.Bullet).where(m.Bullet.firearm_id == fa.id)).all()
                rows: list[tuple[str, Mark]] = []
                for bl in bullets:
                    lands = session.exec(
                        select(m.Land).where(m.Land.bullet_id == bl.id).order_by(m.Land.position)
                    ).all()
                    hashes: list[str] = []
                    for land in lands:
                        scan = session.exec(
                            select(m.Scan).where(m.Scan.land_id == land.id)
                        ).first()
                        if scan is not None:
                            hashes.append(scan.content_hash)
                    if hashes:
                        rows.append(
                            (
                                bl.external_id,
                                Mark(
                                    hash=mark_hash(hashes),
                                    source=source,
                                    label=f"{tag} bullet {bl.external_id}",
                                    scan_hashes=tuple(hashes),
                                ),
                            )
                        )
                if rows:
                    by_barrel.setdefault(source, []).extend(rows)

    # Enumeration order must match build_bullet_pooled_reference exactly, and that
    # builder sorts barrels by its *internal* "study.id:ext" keys — sort the same way.
    barrels = sorted(by_barrel, key=lambda b: npz_src[b])
    study_of = {b: b.split(":")[0] for b in barrels}
    pairs: list[BenchmarkPair] = []
    clusters: list[str] = []

    def _cluster(a: str, b: str) -> str:
        return "|".join(sorted((npz_src[a], npz_src[b])))

    # KM then KNM, mirroring the reference builder's enumeration exactly.
    for src in barrels:
        for (_, ma), (_, mb) in combinations(by_barrel[src], 2):
            pairs.append(make_pair(ma.hash, mb.hash, 1, src, src))
            clusters.append(_cluster(src, src))
    for src_a, src_b in combinations(barrels, 2):
        if study_of[src_a] != study_of[src_b]:
            continue
        for _, ma in by_barrel[src_a]:
            for _, mb in by_barrel[src_b]:
                pairs.append(make_pair(ma.hash, mb.hash, 0, src_a, src_b))
                clusters.append(_cluster(src_a, src_b))

    marks = tuple(mk for src in barrels for _, mk in by_barrel[src])
    datasets = [{"external_id": ext, "tag": tag} for ext, tag in _BULLET_STUDIES.items()]
    return SplitInputs(
        name="bullets-v1",
        title="Bullet lands, pooled (Hamby-252 & 173, PGPD Beretta, Phoenix)",
        modality="striated-bullet",
        score_kind="bullet-contrast",
        reference_npz="bullet_pooled.npz",
        marks=marks,
        pairs=tuple(pairs),
        npz_clusters=tuple(clusters),
        datasets=datasets,
    )


# --------------------------------------------------------------------------- #
# Cartridge cases — single-scan marks from the Fadul cache.
# --------------------------------------------------------------------------- #
def _cartridge_inputs() -> SplitInputs:
    from .cartridge_fadul import _FADUL_RE, fetch_fadul

    masked = fetch_fadul()
    if masked is None:
        raise SystemExit("Fadul cache missing (needs git + network once to fetch)")
    marks: list[tuple[int, Mark]] = []
    for path in sorted(masked.glob("*.x3p")):
        m = _FADUL_RE.search(path.name)
        if not m:
            continue  # questioned (single-letter) set — not in the reference either
        slide = int(m.group(1))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        marks.append(
            (
                slide,
                Mark(
                    hash=digest,
                    source=f"fadul-slide-{slide}",
                    label=path.stem,
                    scan_hashes=(digest,),
                ),
            )
        )

    pairs: list[BenchmarkPair] = []
    clusters: list[str] = []
    for (slide_a, ma), (slide_b, mb) in combinations(marks, 2):
        pairs.append(
            make_pair(ma.hash, mb.hash, 1 if slide_a == slide_b else 0, ma.source, mb.source)
        )
        clusters.append("|".join(sorted((str(slide_a), str(slide_b)))))
    return SplitInputs(
        name="cartridge-v1",
        title="Cartridge breech faces (Fadul, 10 consecutively-manufactured slides)",
        modality="impressed",
        score_kind="cmr-2d",
        reference_npz="cartridge_fadul.npz",
        marks=tuple(mk for _, mk in marks),
        pairs=tuple(pairs),
        npz_clusters=tuple(clusters),
        datasets=[
            {
                "external_id": "fadul-cartridge-cases",
                "tag": "Fadul-2011",
                "source": "CSAFE-ISU/cartridgeCaseScans (fadulMasked, CC-BY 4.0)",
            }
        ],
    )


# --------------------------------------------------------------------------- #
# Toolmarks — single-profile marks from the tmaRks cache, hashed exactly as the
# catalog ingests them (canonical little-endian float64 bytes).
# --------------------------------------------------------------------------- #
def _toolmark_inputs() -> SplitInputs:
    from verity_catalog.toolmarks import _serialize_profile, load_tmarks_profiles

    from .toolmark_tmaRks import DEFAULT_CACHE, source_key

    profiles = load_tmarks_profiles(DEFAULT_CACHE)
    if not profiles:
        raise SystemExit("tmaRks cache missing (run verity-toolmark-tmaRks once to fetch)")
    marks: list[tuple[str, Mark]] = []
    for tid, values in profiles.items():
        edge = source_key(tid, "edge")
        digest = hashlib.sha256(_serialize_profile(values)).hexdigest()
        marks.append((edge, Mark(hash=digest, source=edge, label=tid, scan_hashes=(digest,))))

    pairs: list[BenchmarkPair] = []
    clusters: list[str] = []
    for (edge_a, ma), (edge_b, mb) in combinations(marks, 2):
        pairs.append(
            make_pair(ma.hash, mb.hash, 1 if edge_a == edge_b else 0, ma.source, mb.source)
        )
        clusters.append("|".join(sorted((edge_a, edge_b))))
    return SplitInputs(
        name="toolmark-v1",
        title="Screwdriver toolmarks (tmaRks, consecutively manufactured; tool edges)",
        modality="striated-toolmark",
        score_kind="cmr-1d",
        reference_npz="toolmark_tmaRks.npz",
        marks=tuple(mk for _, mk in marks),
        pairs=tuple(pairs),
        npz_clusters=tuple(clusters),
        datasets=[
            {
                "external_id": "tmaRks-toolmarks",
                "tag": "tmaRks",
                "source": "heike/tmaRks data/toolmarks.rda (MIT)",
            }
        ],
    )


# --------------------------------------------------------------------------- #
# Alignment with the committed reference + dedup + freeze + write.
# --------------------------------------------------------------------------- #
def _aligned_scores(inputs: SplitInputs) -> np.ndarray:
    """Adopt the committed reference's scores after proving this enumeration is
    positionally identical to it (same length, labels, and source clusters)."""
    ref = load_reference(_REF_DIR / inputs.reference_npz)
    labels = np.array([p.label for p in inputs.pairs])
    if len(ref.scores) != len(inputs.pairs):
        raise SystemExit(
            f"{inputs.name}: {len(inputs.pairs)} enumerated pairs vs "
            f"{len(ref.scores)} in {inputs.reference_npz} — regenerate the references "
            "(verity-build-references --write) and retry"
        )
    if not np.array_equal(ref.labels.astype(int), labels):
        raise SystemExit(f"{inputs.name}: label sequence diverges from {inputs.reference_npz}")
    if list(ref.cluster_ids.astype(str)) != list(inputs.npz_clusters):
        raise SystemExit(f"{inputs.name}: cluster sequence diverges from {inputs.reference_npz}")
    prov = ref.provenance or {}
    ref_hash = prov.get("scorer_config_hash")
    if ref_hash and ref_hash != DEFAULT_SCORER_CONFIG.config_hash:
        raise SystemExit(
            f"{inputs.name}: reference scorer_config_hash {ref_hash[:12]} != current "
            f"{DEFAULT_SCORER_CONFIG.config_hash[:12]} — references are off-config"
        )
    return ref.scores


def _dedupe(
    pairs: tuple[BenchmarkPair, ...], scores: np.ndarray
) -> tuple[tuple[BenchmarkPair, ...], np.ndarray, int]:
    """Drop repeated ``pair_id`` rows (possible only when the published data
    contains byte-identical marks — tmaRks has one duplicated profile). The
    first occurrence wins; the count is recorded in provenance."""
    seen: set[str] = set()
    keep: list[int] = []
    for i, p in enumerate(pairs):
        if p.pair_id in seen:
            continue
        seen.add(p.pair_id)
        keep.append(i)
    dropped = len(pairs) - len(keep)
    idx = np.array(keep)
    return tuple(pairs[i] for i in keep), scores[idx], dropped


def _write_csv_gz(path: Path, header: list[str], rows: list[list]) -> None:
    with gzip.open(path, "wt", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


def _fold_membership(pairs: tuple[BenchmarkPair, ...], folds: tuple[FrozenFold, ...]):
    membership: dict[int, list[int]] = {}
    for fold in folds:
        for idx in fold.pair_indices:
            membership.setdefault(idx, []).append(fold.index)
    return membership


def build_split(inputs: SplitInputs, out_root: Path) -> dict:
    scores = _aligned_scores(inputs)
    pairs, scores, n_dup = _dedupe(inputs.pairs, scores)
    folds = freeze_folds(pairs)
    shash = split_hash(pairs, folds)

    print(f"  calibrating Verity's reference submission ({len(pairs)} pairs) ...")
    lrs = loso_lrs(scores, pairs)
    n_nan = int((~np.isfinite(lrs)).sum())
    if n_nan:
        raise SystemExit(f"{inputs.name}: {n_nan} pairs could not be LOSO-calibrated")
    metrics = score_submission(lrs, pairs, folds)

    out = out_root / inputs.name
    out.mkdir(parents=True, exist_ok=True)
    membership = _fold_membership(pairs, folds)
    _write_csv_gz(
        out / "pairs.csv.gz",
        ["pair_id", "hash_a", "hash_b", "label", "source_a", "source_b", "folds"],
        [
            [
                p.pair_id,
                p.hash_a,
                p.hash_b,
                p.label,
                p.source_a,
                p.source_b,
                ";".join(str(f) for f in membership.get(i, [])),
            ]
            for i, p in enumerate(pairs)
        ],
    )
    _write_csv_gz(
        out / "marks.csv.gz",
        ["mark_hash", "source", "label", "n_scans", "scan_hashes"],
        [
            [m.hash, m.source, m.label, len(m.scan_hashes), ";".join(m.scan_hashes)]
            for m in inputs.marks
        ],
    )
    (out / "folds.json").write_text(
        json.dumps(
            [
                {
                    "index": f.index,
                    "n_test_pairs": len(f.pair_indices),
                    "test_sources": list(f.test_sources),
                }
                for f in folds
            ],
            indent=1,
        )
        + "\n"
    )
    _write_csv_gz(
        out / "verity_submission.csv.gz",
        ["pair_id", "lr"],
        [[p.pair_id, f"{lr:.6g}"] for p, lr in zip(pairs, lrs, strict=True)],
    )
    (out / "verity_metrics.json").write_text(json.dumps(metrics, indent=1) + "\n")

    ref_prov = load_reference(_REF_DIR / inputs.reference_npz).provenance or {}
    labels = np.array([p.label for p in pairs])
    provenance = {
        "format_version": 1,
        "protocol_version": PROTOCOL_VERSION,
        "name": inputs.name,
        "title": inputs.title,
        "modality": inputs.modality,
        "split_hash": shash,
        "protocol": {
            "n_splits": DEFAULT_N_SPLITS,
            "test_frac": DEFAULT_TEST_FRAC,
            "seed": DEFAULT_SEED,
            "fold_rule": (
                "repeated source-disjoint splits: per fold, hold out "
                f"round({DEFAULT_TEST_FRAC} * n_sources) sources; a pair is a test pair "
                "iff both its sources are held out; folds keeping <3 train or <1 test "
                "same-source pairs are skipped"
            ),
            "contract": CONTRACT,
            "headline_metric": "calibration_loss (Cllr - Cllr_min, mean over folds)",
        },
        "counts": {
            "n_marks": len(inputs.marks),
            "n_sources": len({p.source_a for p in pairs} | {p.source_b for p in pairs}),
            "n_pairs": len(pairs),
            "n_km": int(labels.sum()),
            "n_knm": int((labels == 0).sum()),
            "n_folds": len(folds),
            "n_duplicate_pairs_dropped": n_dup,
        },
        "scorer": {
            "score_kind": inputs.score_kind,
            "scorer_config_hash": DEFAULT_SCORER_CONFIG.config_hash,
            "reference_npz": inputs.reference_npz,
            "reference_generator": ref_prov.get("generator"),
            "reference_git_commit": ref_prov.get("git_commit"),
        },
        "datasets": inputs.datasets,
        "git_commit": git_short_hash(),
        "verity_baseline": {k: v for k, v in metrics.items() if k != "folds"},
    }
    (out / "provenance.json").write_text(json.dumps(provenance, indent=1) + "\n")
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--only", choices=["bullets-v1", "cartridge-v1", "toolmark-v1"])
    args = parser.parse_args()

    builders = {
        "bullets-v1": _bullet_inputs,
        "cartridge-v1": _cartridge_inputs,
        "toolmark-v1": _toolmark_inputs,
    }
    for name, fn in builders.items():
        if args.only and name != args.only:
            continue
        print(f"{name}:")
        prov = build_split(fn(), args.out)
        c, b = prov["counts"], prov["verity_baseline"]
        print(
            f"  pairs={c['n_pairs']} (KM {c['n_km']}) sources={c['n_sources']} "
            f"folds={c['n_folds']}  split_hash={prov['split_hash'][:16]}…"
        )
        print(
            f"  Verity baseline: Cllr {b['cllr']:.3f}±{b['cllr_std']:.3f} "
            f"Cllr_min {b['cllr_min']:.3f} AUC {b['auc']:.3f} "
            f"calibration loss {b['calibration_loss']:+.3f}"
        )


if __name__ == "__main__":
    main()
