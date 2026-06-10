"""The /benchmark API end-to-end on a synthetic frozen split: load → list →
kit → leaderboard → submit. Hermetic (tmp SQLite, dependency override); also
proves the kit's offline ``evaluate.py`` reproduces the server scoring."""

from __future__ import annotations

import csv
import gzip
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from verity_catalog.api import deps  # noqa: E402
from verity_catalog.api.app import app  # noqa: E402
from verity_catalog.benchmark import scoring  # noqa: E402
from verity_catalog.benchmark.io import read_split_dir  # noqa: E402
from verity_catalog.benchmark.loader import load_split  # noqa: E402


# --------------------------------------------------------------------------- #
# Synthetic split directory (the verity-build-benchmark output format)
# --------------------------------------------------------------------------- #
def _hash(i: int) -> str:
    return f"{i:064x}"


def _make_split_dir(root: Path) -> Path:
    """6 sources × 3 marks, all pairs, 3 hand-frozen source-disjoint folds, and a
    'Verity' submission whose LR is a clean monotone map of a separable score."""
    rng = np.random.default_rng(11)
    marks = [(f"s{s}", _hash(s * 3 + k)) for s in range(6) for k in range(3)]
    pairs = []
    for i in range(len(marks)):
        for j in range(i + 1, len(marks)):
            (sa, ha), (sb, hb) = marks[i], marks[j]
            if hb < ha:
                ha, hb, sa, sb = hb, ha, sb, sa
            label = 1 if sa == sb else 0
            import hashlib

            pid = hashlib.sha256(f"{ha}\n{hb}".encode()).hexdigest()
            pairs.append(
                {
                    "pair_id": pid,
                    "hash_a": ha,
                    "hash_b": hb,
                    "label": label,
                    "source_a": sa,
                    "source_b": sb,
                    "score": float(rng.normal(1.2 * label, 0.4)),
                }
            )

    fold_sources = [{"s0", "s1", "s2"}, {"s2", "s3", "s4"}, {"s0", "s4", "s5"}]
    folds = []
    for k, held in enumerate(fold_sources):
        members = [
            i
            for i, p in enumerate(pairs)
            if p["source_a"] in held and p["source_b"] in held
        ]
        folds.append({"index": k, "n_test_pairs": len(members), "test_sources": sorted(held)})
        for i in members:
            pairs[i].setdefault("_folds", []).append(k)

    split_dir = root / "synthetic-v1"
    split_dir.mkdir(parents=True)
    with gzip.open(split_dir / "pairs.csv.gz", "wt", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pair_id", "hash_a", "hash_b", "label", "source_a", "source_b", "folds"])
        for p in pairs:
            writer.writerow(
                [
                    p["pair_id"],
                    p["hash_a"],
                    p["hash_b"],
                    p["label"],
                    p["source_a"],
                    p["source_b"],
                    ";".join(str(f) for f in p.get("_folds", [])),
                ]
            )
    (split_dir / "folds.json").write_text(json.dumps(folds))

    lrs = np.array([10 ** (2.0 * p["score"] - 1.0) for p in pairs])
    labels = np.array([p["label"] for p in pairs], dtype=float)
    fold_idx = [
        (
            f["index"],
            np.array([i for i, p in enumerate(pairs) if f["index"] in p.get("_folds", [])]),
        )
        for f in folds
    ]
    metrics = scoring.score_submission(lrs, labels, fold_idx)
    with gzip.open(split_dir / "verity_submission.csv.gz", "wt", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pair_id", "lr"])
        for p, lr in zip(pairs, lrs, strict=True):
            writer.writerow([p["pair_id"], f"{lr:.6g}"])
    (split_dir / "verity_metrics.json").write_text(json.dumps(metrics))

    provenance = {
        "format_version": 1,
        "protocol_version": 1,
        "name": "synthetic-v1",
        "title": "Synthetic test split",
        "modality": "striated-test",
        "split_hash": "deadbeef" * 8,
        "protocol": {"contract": "test contract", "seed": 0},
        "counts": {
            "n_marks": len(marks),
            "n_sources": 6,
            "n_pairs": len(pairs),
            "n_km": int(labels.sum()),
            "n_knm": int((labels == 0).sum()),
            "n_folds": len(folds),
            "n_duplicate_pairs_dropped": 0,
        },
        "scorer": {"score_kind": "test", "scorer_config_hash": "0" * 64},
        "datasets": [{"external_id": "synthetic", "tag": "test"}],
        "verity_baseline": {k: v for k, v in metrics.items() if k != "folds"},
    }
    (split_dir / "provenance.json").write_text(json.dumps(provenance))
    return split_dir


@pytest.fixture(autouse=True)
def _fresh_rate_budget():
    """Each test gets a fresh submission-rate window (the TestClient shares one
    client IP across the whole module)."""
    from verity_catalog.api.routers import benchmark as bench_router

    bench_router._rate_hits.clear()
    yield
    bench_router._rate_hits.clear()


@pytest.fixture(scope="module")
def split_env(tmp_path_factory):
    root = tmp_path_factory.mktemp("bench")
    split_dir = _make_split_dir(root)
    artifacts = read_split_dir(split_dir)

    db = create_engine(f"sqlite:///{root / 'bench.db'}")
    SQLModel.metadata.create_all(db)
    with Session(db) as session:
        load_split(session, artifacts)

    def _override():
        with Session(db) as session:
            yield session

    app.dependency_overrides[deps.get_session] = _override
    client = TestClient(app)
    yield client, artifacts, split_dir
    app.dependency_overrides.pop(deps.get_session, None)


# --------------------------------------------------------------------------- #
# Read endpoints
# --------------------------------------------------------------------------- #
def test_list_and_detail(split_env):
    client, artifacts, _ = split_env
    body = client.get("/benchmark/splits").json()
    assert body["success"] is True
    names = [s["name"] for s in body["data"]]
    assert "synthetic-v1" in names

    detail = client.get("/benchmark/splits/synthetic-v1").json()["data"]
    assert detail["split_hash"] == "deadbeef" * 8
    assert detail["n_pairs"] == len(artifacts.pairs)
    assert detail["provenance"]["protocol"]["contract"] == "test contract"
    assert detail["n_submissions"] == 1  # the loaded reference row

    assert client.get("/benchmark/splits/nope").status_code == 404


def test_leaderboard_has_reference_row(split_env):
    client, artifacts, _ = split_env
    rows = client.get("/benchmark/splits/synthetic-v1/leaderboard").json()["data"]
    ref = [r for r in rows if r["is_reference"]]
    assert len(ref) == 1
    assert ref[0]["submitter"] == "Verity"
    assert ref[0]["calibration_loss"] == pytest.approx(
        artifacts.verity_metrics["calibration_loss"]
    )


# --------------------------------------------------------------------------- #
# The kit — offline evaluate.py == server scoring
# --------------------------------------------------------------------------- #
def test_kit_roundtrip_and_offline_evaluation(split_env, tmp_path):
    client, artifacts, _ = split_env
    resp = client.get("/benchmark/splits/synthetic-v1/kit")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = {Path(n).name for n in zf.namelist()}
    assert names == {
        "README.md",
        "pairs.csv.gz",
        "folds.json",
        "provenance.json",
        "scoring.py",
        "evaluate.py",
    }
    kit_dir = tmp_path / "kit"
    zf.extractall(kit_dir)
    (root,) = kit_dir.iterdir()

    with gzip.open(root / "pairs.csv.gz", "rt", newline="") as fh:
        kit_pairs = list(csv.DictReader(fh))
    assert len(kit_pairs) == len(artifacts.pairs)
    assert {p["pair_id"] for p in kit_pairs} == {p["pair_id"] for p in artifacts.pairs}

    submission = root / "sub.csv"
    with submission.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pair_id", "lr"])
        for pid, lr in artifacts.verity_lrs.items():
            writer.writerow([pid, lr])
    out = subprocess.run(
        [sys.executable, str(root / "evaluate.py"), str(submission)],
        capture_output=True,
        text=True,
        check=True,
    )
    offline = json.loads(out.stdout)
    assert offline["split_hash"] == "deadbeef" * 8
    assert offline["cllr"] == pytest.approx(artifacts.verity_metrics["cllr"], rel=1e-6)
    assert offline["calibration_loss"] == pytest.approx(
        artifacts.verity_metrics["calibration_loss"], rel=1e-6
    )


# --------------------------------------------------------------------------- #
# Submissions
# --------------------------------------------------------------------------- #
def test_submit_csv_scores_and_ranks(split_env):
    client, artifacts, _ = split_env
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["pair_id", "lr"])
    for pid in artifacts.verity_lrs:
        writer.writerow([pid, 1.0])  # the uninformative submission: LR=1 everywhere
    resp = client.post(
        "/benchmark/splits/synthetic-v1/submissions",
        json={"submitter": "tester", "method": "always-one", "csv": buf.getvalue()},
    )
    assert resp.status_code == 201, resp.text
    metrics = resp.json()["data"]["metrics"]
    assert metrics["cllr"] == pytest.approx(1.0)  # LR=1 → exactly the uninformative cost

    rows = client.get("/benchmark/splits/synthetic-v1/leaderboard").json()["data"]
    # Ranked by total Cllr: the informative reference beats the LR=1 trivial
    # submission even though the trivial one has zero calibration loss.
    assert [r["submitter"] for r in rows][0] == "Verity"
    assert any(r["submitter"] == "tester" for r in rows)


def test_submit_lrs_object(split_env):
    client, artifacts, _ = split_env
    resp = client.post(
        "/benchmark/splits/synthetic-v1/submissions",
        json={
            "submitter": "tester2",
            "method": "verity-copy",
            "lrs": artifacts.verity_lrs,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["metrics"]["cllr"] == pytest.approx(
        artifacts.verity_metrics["cllr"], rel=1e-6
    )


def test_submit_rejections(split_env):
    client, artifacts, _ = split_env
    url = "/benchmark/splits/synthetic-v1/submissions"
    some = dict(list(artifacts.verity_lrs.items())[:3])

    # Coverage mismatch.
    r = client.post(url, json={"submitter": "x", "method": "m", "lrs": some})
    assert r.status_code == 422 and "coverage" in r.json()["error"]

    # Junk LRs.
    bad = {pid: -1.0 for pid in artifacts.verity_lrs}
    r = client.post(url, json={"submitter": "x", "method": "m", "lrs": bad})
    assert r.status_code == 422 and "positive" in r.json()["error"]

    # Exactly one of lrs/csv.
    r = client.post(url, json={"submitter": "x", "method": "m"})
    assert r.status_code == 422
    r = client.post(
        url, json={"submitter": "x", "method": "m", "lrs": some, "csv": "pair_id,lr\n"}
    )
    assert r.status_code == 422


def test_rate_limit(split_env, monkeypatch):
    from verity_catalog.api.routers import benchmark as bench_router

    client, artifacts, _ = split_env
    monkeypatch.setattr(bench_router, "_RATE_LIMIT", 1)
    bench_router._rate_hits.clear()
    url = "/benchmark/splits/synthetic-v1/submissions"
    payload = {"submitter": "x", "method": "m", "lrs": artifacts.verity_lrs}
    assert client.post(url, json=payload).status_code == 201
    assert client.post(url, json=payload).status_code == 429
    bench_router._rate_hits.clear()


def test_submit_token_gate(split_env, monkeypatch):
    from verity_catalog.api.routers import benchmark as bench_router

    client, artifacts, _ = split_env
    bench_router._rate_hits.clear()
    monkeypatch.setenv("VERITY_BENCHMARK_SUBMIT_TOKEN", "sekrit")
    url = "/benchmark/splits/synthetic-v1/submissions"
    payload = {"submitter": "x", "method": "m", "lrs": artifacts.verity_lrs}
    assert client.post(url, json=payload).status_code == 403
    assert (
        client.post(url, json=payload, headers={"X-Benchmark-Token": "sekrit"}).status_code
        == 201
    )
