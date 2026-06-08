"""The central scorer config + drift guard."""

from __future__ import annotations

import dataclasses

import pytest

from verity.decision.scorer_config import (
    DEFAULT_SCORER_CONFIG,
    ScorerConfig,
    ScorerConfigDrift,
    check_scorer_drift,
)


def test_default_matches_deployed_constants():
    c = DEFAULT_SCORER_CONFIG
    assert (c.lambda_s, c.lambda_c) == (4e-6, 250e-6)
    assert c.cmr_corr == 0.3 and tuple(c.cmr_tol) == (20.0, 20.0, 6.0)
    assert (c.cmr_1d_corr, c.cmr_1d_lag) == (0.5, 10.0)
    assert c.name == "bullet-contrast"


def test_config_hash_is_stable_and_sensitive():
    h = DEFAULT_SCORER_CONFIG.config_hash
    assert h == ScorerConfig().config_hash  # deterministic across instances
    assert dataclasses.replace(DEFAULT_SCORER_CONFIG, cmr_corr=0.31).config_hash != h
    assert dataclasses.replace(DEFAULT_SCORER_CONFIG, name="other").config_hash != h


def test_to_dict_is_json_friendly():
    import json

    json.dumps(DEFAULT_SCORER_CONFIG.to_dict())  # must not raise
    assert DEFAULT_SCORER_CONFIG.to_dict()["cmr_tol"] == [20.0, 20.0, 6.0]


def test_drift_silent_when_absent_or_matching(recwarn):
    assert check_scorer_drift(None, reference_name="legacy") is True
    assert check_scorer_drift(DEFAULT_SCORER_CONFIG.config_hash, reference_name="ok") is True
    assert len(recwarn) == 0


def test_drift_warns_by_default():
    with pytest.warns(UserWarning):
        assert check_scorer_drift("deadbeef", reference_name="stale") is False


def test_drift_raises_under_strict(monkeypatch):
    monkeypatch.setenv("VERITY_STRICT_REFERENCE", "1")
    with pytest.raises(ScorerConfigDrift):
        check_scorer_drift("deadbeef", reference_name="stale")
