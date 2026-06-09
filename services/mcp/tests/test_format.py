"""Agent-facing formatting: the summary an LLM sees, including honest refusals.

These cover the pure formatter (no network, no MCP), so they run with only pytest. The
HTTP path is smoke-tested against a live API in the README / CI separately.
"""

from __future__ import annotations

from verity_mcp.api import _human_lr, summarize_compare


def test_summarize_calibrated_trims_previews_and_keeps_handle():
    report = {
        "domain": "impressed",
        "likelihood_ratio": 146.0,
        "log10_lr": 2.16,
        "log10_lr_ci_lo": 1.74,
        "log10_lr_ci_hi": 2.16,
        "lr_bound_log10": 2.16,
        "direction": "same source",
        "verbal": "moderately strong support for same source",
        "reference": {
            "name": "Fadul",
            "n_km": 10,
            "n_knm": 180,
            "auc": 0.997,
            "cllr": 0.22,
            "cllr_min": 0.07,
        },
        "attribution": [{"x": 0}, {"x": 1}],
        "handle": "sha256:abc123",
        "scope_note": "calibrated weight of evidence …",
        "scope": {"mark_a": [{"name": "resolution", "passed": True}], "mark_b": []},
        "previews": {"a": [[1, 2]], "b": [[3, 4]]},  # bulky — must be dropped
    }
    s = summarize_compare(report)
    assert s["status"] == "calibrated"
    assert s["likelihood_ratio"] == 146.0 and s["handle"] == "sha256:abc123"
    assert s["log10_lr_ci"] == [1.74, 2.16]
    assert s["attribution_regions"] == 2
    assert s["reference"]["name"] == "Fadul"
    assert "previews" not in s  # trimmed for the agent
    assert "Reproducible recipe handle" in s["summary"]


def test_summarize_refused_relays_reason():
    s = summarize_compare(
        {
            "refused": True,
            "domain": "striated",
            "reason": "lateral pitch too coarse",
            "scope_note": "x",
        }
    )
    assert s["status"] == "refused" and "coarse" in s["reason"]
    assert "likelihood_ratio" not in s


def test_summarize_off_config_is_uncalibrated_not_fabricated():
    s = summarize_compare(
        {
            "calibrated": False,
            "domain": "impressed",
            "score": 3.0,
            "uncalibrated_reason": "scorer config does not match the reference's",
            "requested_scorer_config_hash": "aaa",
            "reference_scorer_config_hash": "bbb",
        }
    )
    assert s["status"] == "uncalibrated"
    assert s["score"] == 3.0 and "likelihood_ratio" not in s
    assert s["requested_scorer_config_hash"] == "aaa"


def test_scope_warnings_surfaced():
    report = {
        "domain": "impressed",
        "likelihood_ratio": 1.0,
        "reference": {},
        "attribution": [],
        "handle": "h",
        "scope": {
            "mark_a": [
                {"name": "signal", "passed": False, "reason": "low RMS", "severity": "warn"}
            ],
            "mark_b": [],
        },
    }
    s = summarize_compare(report)
    assert any("signal" in w for w in s["scope_warnings"])


def test_human_lr():
    assert _human_lr(146.0) == "146x"
    assert _human_lr(0.002).startswith("1/")
    assert _human_lr(None) == "—"
