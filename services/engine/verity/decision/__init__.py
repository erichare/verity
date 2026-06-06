"""The transparent calibrated decision layer: score → likelihood ratio, and the
forensic metrics to validate it."""

from .lr import ScoreLRModel, cllr_min
from .metrics import cllr, ece, eer, lr_separation, margin, roc_auc, tippett

__all__ = [
    "ScoreLRModel",
    "cllr",
    "cllr_min",
    "ece",
    "eer",
    "lr_separation",
    "margin",
    "roc_auc",
    "tippett",
]
