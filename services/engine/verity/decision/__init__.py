"""The transparent calibrated decision layer: score → likelihood ratio, and the
forensic metrics to validate it."""

from .lr import ScoreLRModel, cllr_min
from .metrics import cllr, ece, eer, lr_separation, margin, roc_auc, tippett
from .scope_guard import ScopeCheck, ScopeReport, check_applicability
from .scorer import BulletScorer, ContrastScorer, FusionScorer
from .scorer_config import (
    DEFAULT_SCORER_CONFIG,
    ScorerConfig,
    ScorerConfigDrift,
    check_scorer_drift,
)
from .uncertainty import (
    BootstrapCalibration,
    LRInterval,
    cached_bootstrap_calibration,
    lr_credible_interval,
)

__all__ = [
    "DEFAULT_SCORER_CONFIG",
    "ScoreLRModel",
    "BootstrapCalibration",
    "BulletScorer",
    "ContrastScorer",
    "FusionScorer",
    "LRInterval",
    "ScopeCheck",
    "ScopeReport",
    "ScorerConfig",
    "ScorerConfigDrift",
    "cached_bootstrap_calibration",
    "check_applicability",
    "check_scorer_drift",
    "cllr",
    "cllr_min",
    "ece",
    "eer",
    "lr_credible_interval",
    "lr_separation",
    "margin",
    "roc_auc",
    "tippett",
]
