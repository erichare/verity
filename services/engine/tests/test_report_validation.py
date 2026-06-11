"""Tests for the validation-report generator (PDF + JSON summary)."""

from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("matplotlib")

from verity.examples._reference_io import write_reference  # noqa: E402
from verity.report_validation import (  # noqa: E402
    compute_validation_summary,
    generate_validation_report,
    report_from_reference,
)


def _synthetic_pairs(seed: int = 0):
    """Mimic ``pairwise_scores`` output: scores + KM/KNM labels + barrels per side.
    8 barrels; same-barrel pairs score high, cross-barrel low."""
    rng = np.random.default_rng(seed)
    scores: list[float] = []
    labels: list[int] = []
    ba: list[int] = []
    bb: list[int] = []
    n_barrels = 8
    for i in range(n_barrels):
        for j in range(i, n_barrels):
            same = i == j
            for _ in range(6 if same else 4):
                scores.append(float(rng.normal(2.5 if same else -0.5, 1.0)))
                labels.append(1 if same else 0)
                ba.append(i)
                bb.append(j)
    return np.array(scores), np.array(labels, dtype=float), np.array(ba), np.array(bb)


def test_summary_without_barrels_has_no_disjoint():
    scores, labels, _ba, _bb = _synthetic_pairs()
    s = compute_validation_summary(scores, labels, reference_name="synthetic", domain="striated")
    assert s.n_km > 0 and s.n_knm > 0
    assert s.n_sources is None
    assert s.barrel_disjoint is None
    assert s.cllr >= s.cllr_min - 1e-9  # Cllr_min is the floor
    assert 0.0 <= s.auc <= 1.0


def test_summary_with_barrels_has_disjoint():
    scores, labels, ba, bb = _synthetic_pairs()
    s = compute_validation_summary(
        scores,
        labels,
        reference_name="synthetic",
        domain="striated",
        barrels_a=ba,
        barrels_b=bb,
    )
    assert s.n_sources == 8
    assert s.barrel_disjoint is not None
    assert s.barrel_disjoint["n_folds"] >= 1
    assert "cllr_mean" in s.barrel_disjoint


def test_generate_validation_report_writes_pdf_and_json(tmp_path):
    scores, labels, ba, bb = _synthetic_pairs()
    out = tmp_path / "report.pdf"
    summary = generate_validation_report(
        scores,
        labels,
        reference_name="synthetic reference",
        domain="striated",
        out_path=str(out),
        barrels_a=ba,
        barrels_b=bb,
        generated_at="2026-06-07",
    )
    assert out.exists() and out.stat().st_size > 1000  # a real multi-page PDF
    assert out.read_bytes()[:4] == b"%PDF"
    sidecar = out.with_suffix(".json")
    assert sidecar.exists()
    loaded = json.loads(sidecar.read_text())
    assert loaded["reference_name"] == "synthetic reference"
    assert loaded["pipeline_version"] == summary.pipeline_version
    assert loaded["barrel_disjoint"]["n_folds"] >= 1


def test_report_from_reference_recovers_sources(tmp_path):
    """A committed reference bundle (scores/labels/pair-source-set clusters) renders a
    validation PDF + source-disjoint summary with no catalog — the impressed/toolmark
    path. Sources are recovered from the 'A|B' cluster IDs."""
    scores, labels, ba, bb = _synthetic_pairs()
    clusters = [f"{min(a, b)}|{max(a, b)}" for a, b in zip(ba, bb, strict=True)]
    ref = tmp_path / "synthetic_impressed.npz"
    write_reference(
        ref, scores=scores, labels=labels, cluster_ids=clusters,
        name="synthetic impressed", generator="test", seed=0, datasets=[], write=True,
    )
    out = tmp_path / "impressed_report.pdf"
    summary = report_from_reference(ref, domain="impressed", out_path=str(out))
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"
    assert summary.domain == "impressed"
    assert summary.reference_name == "synthetic impressed"  # picked up from provenance
    assert summary.n_sources == 8  # all barrels recovered from the cluster IDs
    assert summary.barrel_disjoint is not None and summary.barrel_disjoint["n_folds"] >= 1
