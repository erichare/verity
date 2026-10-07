"""Test the court-ready per-comparison PDF renderer."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("matplotlib")

from verity.report_pdf import render_comparison_pdf  # noqa: E402


def _report() -> dict:
    grid = np.clip(np.random.default_rng(0).normal(0.5, 0.2, (40, 60)), 0, 1).round(3).tolist()
    return {
        "domain": "striated",
        "score": 0.153,
        "score_kind": "bullet-contrast",
        "likelihood_ratio": 146.0,
        "log10_lr": 2.16,
        "log10_lr_ci_lo": 1.83,
        "log10_lr_ci_hi": 2.16,
        "direction": "same source",
        "verbal": "moderately strong support for same source",
        "lr_bound_log10": 2.16,
        "reference": {
            "name": "pooled bullet-land reference",
            "n_km": 146,
            "n_knm": 1755,
            "cllr": 0.193,
            "cllr_min": 0.168,
            "auc": 0.984,
        },
        "attribution": [{"x_frac": 0.1, "y_frac": 0.0, "w_frac": 0.15, "h_frac": 1.0, "corr": 0.9}],
        "attribution_b": [
            {"x_frac": 0.12, "y_frac": 0.0, "w_frac": 0.15, "h_frac": 1.0, "corr": 0.9}
        ],
        "provenance": {
            "engine_version": "0.1.0",
            "api_version": "0.1.0",
            "scorer": "bullet-contrast",
            "input_hashes": {"mark_a": ["a" * 64], "mark_b": ["b" * 64]},
        },
        "scope_note": "This is a calibrated weight of evidence on a named reference. "
        "It is not a verdict: it is one input to an examiner's judgment, alongside "
        "case context. It is not a claim about the error rate of striated examination.",
        "previews": {"a": grid, "b": grid},
    }


def test_render_comparison_pdf_writes_two_page_pdf(tmp_path):
    out = tmp_path / "comparison.pdf"
    render_comparison_pdf(_report(), str(out), case_id="DEMO-1", examiner="E. Hare")
    assert out.exists() and out.stat().st_size > 1000
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_comparison_pdf_without_previews(tmp_path):
    rep = _report()
    rep["previews"] = {}  # no attribution page, still renders the findings page
    out = tmp_path / "c2.pdf"
    render_comparison_pdf(rep, str(out))
    assert out.exists() and out.read_bytes()[:4] == b"%PDF"


def test_pdf_keeps_diagnostic_restriction_and_all_scope_warnings(tmp_path, monkeypatch):
    from matplotlib.backends.backend_pdf import PdfPages

    captured = []
    original_savefig = PdfPages.savefig

    def capture(self, figure, *args, **kwargs):
        captured.append("\n".join(text.get_text() for text in figure.texts))
        return original_savefig(self, figure, *args, **kwargs)

    monkeypatch.setattr(PdfPages, "savefig", capture)
    report = _report()
    report["evidence_note"] = {
        "level": "diagnostic_only",
        "reason": "Diagnostic only, not reportable evidence.",
    }
    report["scope"] = {
        "mark_a": [
            {
                "checks": [
                    {"name": "signal", "passed": False, "reason": f"Weak texture check {i}"}
                    for i in range(60)
                ]
            }
        ]
    }
    render_comparison_pdf(report, str(tmp_path / "diagnostic.pdf"))
    assert "Diagnostic only" in captured[0]
    all_text = "\n".join(captured)
    assert "not reportable evidence" in all_text
    for i in range(60):
        assert f"Weak texture check {i}" in all_text
