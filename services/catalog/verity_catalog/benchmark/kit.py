"""The downloadable replication kit — everything a collaborator needs to score
a submission *offline* and verify it matches the leaderboard exactly.

A kit zip contains the frozen ``pairs.csv.gz`` + ``folds.json`` +
``provenance.json`` (with the ``split_hash``), the ``marks.csv.gz``
mark-hash → scan-hash mapping when the split ships one, this package's
``scoring.py`` verbatim (numpy-only), a standalone ``evaluate.py`` CLI, and a
README stating the protocol + submission contract. Offline ``evaluate.py``
output equals the server's ``POST /benchmark/splits/{name}/submissions``
scoring by construction: both run the same ``scoring.py`` on the same frozen
rows.

The README's submission instructions point at this API's public base URL,
configurable via the ``VERITY_CATALOG_PUBLIC_URL`` env var (default
``https://data.verity.codes``) so kits stay followable wherever the service is
hosted.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import zipfile
from importlib import resources

from .. import models

DEFAULT_PUBLIC_URL = "https://data.verity.codes"

# split.id -> (split_hash, public_url, kit bytes)
_KIT_CACHE: dict[int, tuple[str, str, bytes]] = {}


def _public_url() -> str:
    """The public base URL baked into kit instructions (no trailing slash)."""
    configured = os.environ.get("VERITY_CATALOG_PUBLIC_URL", "").strip()
    return (configured or DEFAULT_PUBLIC_URL).rstrip("/")


_EVALUATE_PY = '''\
"""Score a benchmark submission offline — identical to the leaderboard scoring.

    python evaluate.py my_submission.csv

The submission is a CSV with a ``pair_id,lr`` header: one finite, strictly
positive likelihood ratio for every pair in ``pairs.csv.gz`` (exact coverage).
Requires numpy; ``scoring.py`` (shipped in this kit) must sit next to this file.
"""

import csv
import gzip
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scoring  # noqa: E402  (the kit's verbatim copy of the server scorer)

HERE = Path(__file__).resolve().parent


def read_pairs():
    with gzip.open(HERE / "pairs.csv.gz", "rt", newline="") as fh:
        return list(csv.DictReader(fh))


def read_submission(path):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", newline="") as fh:
        reader = csv.DictReader(fh)
        if "pair_id" not in reader.fieldnames or "lr" not in reader.fieldnames:
            raise SystemExit("submission needs a 'pair_id,lr' header")
        return {row["pair_id"]: float(row["lr"]) for row in reader}


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    pairs = read_pairs()
    lrs_by_id = read_submission(sys.argv[1])

    wanted = {p["pair_id"] for p in pairs}
    missing = wanted - set(lrs_by_id)
    unknown = set(lrs_by_id) - wanted
    if missing or unknown:
        raise SystemExit(
            f"coverage mismatch: {len(missing)} pair(s) missing, "
            f"{len(unknown)} unknown pair id(s) — submit exactly one LR per frozen pair"
        )

    lrs = np.array([lrs_by_id[p["pair_id"]] for p in pairs])
    labels = np.array([int(p["label"]) for p in pairs], dtype=float)
    fold_members = {}
    for i, p in enumerate(pairs):
        for f in p["folds"].split(";"):
            if f:
                fold_members.setdefault(int(f), []).append(i)
    folds = [(k, np.array(v)) for k, v in sorted(fold_members.items())]

    metrics = scoring.score_submission(lrs, labels, folds)
    provenance = json.loads((HERE / "provenance.json").read_text())
    print(json.dumps({"split": provenance["name"], "split_hash": provenance["split_hash"],
                      **{k: v for k, v in metrics.items() if k != "folds"}}, indent=1))


if __name__ == "__main__":
    main()
'''

_README = """\
# Verity open benchmark — replication kit: {name}

{title}

* split_hash: `{split_hash}`
* pairs: {n_pairs} ({n_km} same-source / {n_knm} different-source)
* sources: {n_sources}, frozen folds: {n_folds}
* headline metric: calibration loss (Cllr − Cllr_min, mean over source-disjoint folds)

## Contents

* `pairs.csv.gz`     — the frozen pairs: `pair_id,hash_a,hash_b,label,source_a,source_b,folds`.
  `hash_a`/`hash_b` are SHA-256 content hashes of the marks (a multi-scan mark hashes its
  sorted scan hashes); `folds` lists the fold indices in which the pair is a *test* pair.
{marks_entry}* `folds.json`       — each frozen fold's held-out source set.
* `provenance.json`  — protocol, scorer config hash, datasets, and the `split_hash`.
* `scoring.py`       — the scorer (numpy-only), byte-identical to the leaderboard's.
* `evaluate.py`      — score a submission offline: `python evaluate.py my_submission.csv`.

## The submission contract

{contract}

A submission CSV has a `pair_id,lr` header and exactly one finite, strictly
positive likelihood ratio per frozen pair. Offline `evaluate.py` output equals
the leaderboard scoring; submit via:

    POST {public_url}/benchmark/splits/{name}/submissions
    {{"submitter": "you", "method": "your-method", "url": "https://…", "csv": "<pair_id,lr…>"}}

The underlying scans are public: resolve any `hash_a`/`hash_b` against the
Verity catalog (https://verity.codes/catalog, content-addressed) or recompute
the hashes from the source datasets listed in `provenance.json`.
"""

_MARKS_ENTRY = """\
* `marks.csv.gz`     — the mark-hash → scan mapping:
  `mark_hash,source,label,n_scans,scan_hashes` (`scan_hashes` is ";"-joined).
  Composite (multi-scan) `hash_a`/`hash_b` values resolve to their individual
  scan content hashes here.
"""


def build_kit(split: models.BenchmarkSplit, pairs: list[models.BenchmarkPair]) -> bytes:
    """Assemble (and memoize, keyed by split_hash + public URL) the kit zip."""
    public_url = _public_url()
    cached = _KIT_CACHE.get(split.id)
    if cached is not None and cached[0] == split.split_hash and cached[1] == public_url:
        return cached[2]

    prov = json.loads(split.provenance)
    pairs_buf = io.BytesIO()
    with gzip.GzipFile(fileobj=pairs_buf, mode="wb", mtime=0) as gz:
        text = io.TextIOWrapper(gz, write_through=True, newline="")
        writer = csv.writer(text)
        writer.writerow(["pair_id", "hash_a", "hash_b", "label", "source_a", "source_b", "folds"])
        for p in pairs:
            writer.writerow(
                [p.pair_id, p.hash_a, p.hash_b, p.label, p.source_a, p.source_b, p.folds]
            )
        text.flush()

    folds_json = json.dumps(
        [
            {
                "index": f.fold_index,
                "n_test_pairs": f.n_test_pairs,
                "test_sources": json.loads(f.test_sources),
            }
            for f in sorted(split.folds, key=lambda f: f.fold_index)
        ],
        indent=1,
    )
    scoring_src = resources.files("verity_catalog.benchmark").joinpath("scoring.py").read_text()
    marks = split.marks_csv_gz
    readme = _README.format(
        name=split.name,
        title=split.title,
        split_hash=split.split_hash,
        n_pairs=split.n_pairs,
        n_km=split.n_km,
        n_knm=split.n_pairs - split.n_km,
        n_sources=split.n_sources,
        n_folds=split.n_folds,
        contract=prov.get("protocol", {}).get("contract", ""),
        marks_entry=_MARKS_ENTRY if marks else "",
        public_url=public_url,
    )

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        root = f"verity-benchmark-{split.name}"
        zf.writestr(f"{root}/README.md", readme)
        zf.writestr(f"{root}/pairs.csv.gz", pairs_buf.getvalue())
        if marks:
            zf.writestr(f"{root}/marks.csv.gz", marks)
        zf.writestr(f"{root}/folds.json", folds_json + "\n")
        zf.writestr(f"{root}/provenance.json", split.provenance)
        zf.writestr(f"{root}/scoring.py", scoring_src)
        zf.writestr(f"{root}/evaluate.py", _EVALUATE_PY)
    data = out.getvalue()
    _KIT_CACHE[split.id] = (split.split_hash, public_url, data)
    return data
