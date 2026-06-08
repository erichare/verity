"""Build the single-land striated reference (land-to-land CCF, KM vs KNM).

The bullet reference (``bullet_pooled.npz``) calibrates *bullet* comparisons
(several lands aggregated). A single land is a different — and much weaker —
comparison object: its score is one land-to-land cross-correlation, with no
land x land matrix to read structure from. Calibrating a single land against the
bullet reference saturates the LR; it needs its own reference.

This pools same-barrel (KM) and different-barrel (KNM) land-pair CCFs from the
cached studies into ``striated_land.npz``. Run from the repo root:

    uv --directory services/engine run python -m verity.examples.build_striated_land_reference
"""

from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

from verity.decision.scorer_config import DEFAULT_SCORER_CONFIG
from verity.registration.align import align_1d
from verity.signature import striation_signature
from verity.surface import Surface

from ._reference_io import write_reference

_LAMBDA_S, _LAMBDA_C = DEFAULT_SCORER_CONFIG.lambda_s, DEFAULT_SCORER_CONFIG.lambda_c
_ROOT = Path(__file__).resolve().parents[4]  # repo root, regardless of CWD
_CACHE = _ROOT / "services/catalog/.verity/cache/bulletxtrctr"
_OUT = _ROOT / "services/api/verity_api/references/striated_land.npz"
_N_KM, _N_KNM = 2000, 4000  # different-source is the broader prior


def _signature(x3p_path: Path) -> np.ndarray:
    import verity_x3p

    s = verity_x3p.read_x3p(str(x3p_path))
    surf = Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)
    return striation_signature(surf, lambda_s=_LAMBDA_S, lambda_c=_LAMBDA_C)


def _load_lands() -> list[tuple[str, int, np.ndarray]]:
    lands: list[tuple[str, int, np.ndarray]] = []
    for study in sorted(p for p in _CACHE.iterdir() if (p / "manifest.csv").exists()):
        for r in csv.DictReader((study / "manifest.csv").open()):
            f = study / "x3p" / f"{r['file']}.x3p"
            if f.exists():
                lands.append((study.name, int(r["barrel"]), _signature(f)))
    return lands


def main() -> None:
    rng = random.Random(0)
    lands = _load_lands()
    by_barrel: dict[tuple[str, int], list[int]] = defaultdict(list)
    for i, (study, barrel, _) in enumerate(lands):
        by_barrel[(study, barrel)].append(i)
    keys = list(by_barrel)
    by_study: dict[str, list] = defaultdict(list)
    for k in keys:
        by_study[k[0]].append(k)
    print(f"{len(lands)} lands, {len(keys)} barrels across {len(by_study)} studies")

    def sample(want: int, same_barrel: bool) -> list[tuple[int, int]]:
        out: set[tuple[int, int]] = set()
        for _ in range(want * 60):
            if len(out) >= want:
                break
            study = rng.choice(list(by_study))
            sk = by_study[study]
            if same_barrel:
                idx = by_barrel[rng.choice(sk)]
                if len(idx) < 2:
                    continue
                a, b = rng.sample(idx, 2)
            else:
                if len(sk) < 2:
                    continue
                ka, kb = rng.sample(sk, 2)
                a, b = rng.choice(by_barrel[ka]), rng.choice(by_barrel[kb])
            out.add((min(a, b), max(a, b)))
        return list(out)

    km_pairs = sample(_N_KM, True)
    knm_pairs = sample(_N_KNM, False)

    def ccf(a: int, b: int) -> float:
        return float(align_1d(lands[a][2], lands[b][2])[1])

    def cluster_key(a: int, b: int) -> str:
        ka, kb = f"{lands[a][0]}:{lands[a][1]}", f"{lands[b][0]}:{lands[b][1]}"
        return "|".join(sorted((ka, kb)))

    pairs = km_pairs + knm_pairs
    scores = np.array([ccf(a, b) for a, b in pairs])
    labels = np.r_[np.ones(len(km_pairs)), np.zeros(len(knm_pairs))]
    clusters = [cluster_key(a, b) for a, b in pairs]

    art = write_reference(
        _OUT,
        scores=scores,
        labels=labels,
        cluster_ids=clusters,
        name="pooled single-land reference (Hamby-252, Beretta)",
        generator="build_striated_land_reference",
        seed=0,
        datasets=[{"source": "bulletxtrctr-cache", "tag": "single-land", "n_lands": len(lands)}],
        write="--write" in sys.argv,
    )
    d = art.provenance["diagnostics"]
    print(
        f"n_km={d['n_km']} n_knm={d['n_knm']} n_sources={art.provenance['n_sources']} "
        f"AUC={d['auc']:.3f} Cllr_min={d['cllr_min']:.3f}"
    )
    print(f"{'WROTE' if '--write' in sys.argv else 'DRY-RUN (pass --write to save)'}: {_OUT}")


if __name__ == "__main__":
    main()
