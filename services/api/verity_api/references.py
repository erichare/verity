"""Bundled reference populations for calibration.

To report a likelihood ratio, a comparison score must be calibrated against a
named reference population's KM/KNM scores (same scorer). The API ships a small
reference per domain so it can calibrate without the full corpus at runtime. The
reference both fits the score→LR map and scopes it ("calibrated on dataset D").
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from verity.decision import check_scorer_drift

from .reference_bundle import ReferenceBundle, load_bundle

_DIR = Path(__file__).parent / "references"

# domain -> (file, human-readable reference name)
_REFERENCES = {
    "impressed": ("cartridge_fadul.npz", "Fadul cartridge cases (10 consecutively-manufactured slides)"),
    "striated": ("bullet_pooled.npz", "pooled bullet-land reference (Hamby-252 & 173, Beretta, Phoenix)"),
}

# A single striated land is a weaker comparison object than a whole bullet, scored on
# one land-to-land CCF — it must be calibrated against single-land (not bullet) scores.
_STRIATED_SINGLE = ("striated_land.npz", "pooled single-land reference (Hamby-252, Beretta)")


def available_domains() -> list[str]:
    return sorted(_REFERENCES)


def _load_checked(fname: str, name: str) -> ReferenceBundle:
    """Load a bundle and run the scorer-config drift guard (warn by default; raises
    under VERITY_STRICT_REFERENCE so a stale reference can't silently ship a bad LR)."""
    bundle = load_bundle(_DIR / fname, name=name)
    check_scorer_drift(bundle.scorer_config_hash, reference_name=name)
    return bundle


def load_striated_single_bundle() -> ReferenceBundle:
    """The single-land striated reference as a bundle (scores, labels, cluster IDs)."""
    return _load_checked(*_STRIATED_SINGLE)


def load_reference_bundle(domain: str) -> ReferenceBundle:
    """A domain's bundled reference as a :class:`ReferenceBundle`."""
    if domain not in _REFERENCES:
        raise KeyError(domain)
    return _load_checked(*_REFERENCES[domain])


def load_striated_single_land() -> tuple[np.ndarray, np.ndarray, str]:
    """Return ``(scores, labels, name)`` for the single-land striated reference."""
    b = load_striated_single_bundle()
    return b.scores, b.labels, b.name


def load_reference(domain: str) -> tuple[np.ndarray, np.ndarray, str]:
    """Return ``(scores, labels, name)`` for a domain's bundled reference."""
    b = load_reference_bundle(domain)
    return b.scores, b.labels, b.name
