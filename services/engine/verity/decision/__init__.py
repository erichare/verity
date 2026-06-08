"""The transparent calibrated decision layer: score → likelihood ratio, and the
forensic metrics to validate it."""

from .lr import ScoreLRModel, cllr_min
from .metrics import cllr, ece, eer, lr_separation, margin, roc_auc, tippett
from .scorer import BulletScorer, ContrastScorer, FusionScorer
from .uncertainty import (
    BootstrapCalibration,
    LRInterval,
    cached_bootstrap_calibration,
    lr_credible_interval,
)

__all__ = [
    "ScoreLRModel",
    "BootstrapCalibration",
    "BulletScorer",
    "ContrastScorer",
    "FusionScorer",
    "LRInterval",
    "cached_bootstrap_calibration",
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
