"""Verity — a domain-general surface-comparison engine.

Phase 1: surface-metrology preprocessing (form removal + ISO 16610 S/L
filtering to isolate the individualizing roughness band), dominant-orientation
detection, striation-signature extraction, and a registration dispatcher (1-D
cross-correlation for striated marks, 2-D phase correlation for areal marks).
The learned representation + calibrated likelihood-ratio decision layer come in
later phases.
"""

from .aggregate import BulletComparison, bullet_comparison, bullet_score, land_ccf_matrix
from .decision import (
    BootstrapCalibration,
    LRInterval,
    ScoreLRModel,
    cached_bootstrap_calibration,
    cllr,
    cllr_min,
    ece,
    eer,
    lr_credible_interval,
    lr_separation,
    margin,
    roc_auc,
    tippett,
)
from .orientation import dominant_orientation
from .preprocess import gaussian_lowpass, isolate_roughness, remove_form, sa, sq
from .registration import Registration, align_1d, register
from .signature import striation_signature
from .surface import Surface
from .trace import LandTrace, land_trace

__version__ = "0.1.0"

__all__ = [
    "Surface",
    "remove_form",
    "gaussian_lowpass",
    "isolate_roughness",
    "sa",
    "sq",
    "dominant_orientation",
    "striation_signature",
    "register",
    "Registration",
    "align_1d",
    "bullet_score",
    "bullet_comparison",
    "BulletComparison",
    "land_ccf_matrix",
    "land_trace",
    "LandTrace",
    "ScoreLRModel",
    "BootstrapCalibration",
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
