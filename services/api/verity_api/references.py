"""Bundled reference populations for calibration.

To report a likelihood ratio, a comparison score must be calibrated against a
named reference population's KM/KNM scores (same scorer). The API ships a small
reference per domain so it can calibrate without the full corpus at runtime. The
reference both fits the score→LR map and scopes it ("calibrated on dataset D").
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

_DIR = Path(__file__).parent / "references"

# domain -> (file, human-readable reference name)
_REFERENCES = {
    "impressed": ("cartridge_fadul.npz", "Fadul cartridge cases (10 consecutively-manufactured slides)"),
    "striated": ("bullet_pooled.npz", "pooled bullet-land reference (Hamby-252 & 173, Beretta, Phoenix)"),
}


def available_domains() -> list[str]:
    return sorted(_REFERENCES)


def load_reference(domain: str) -> tuple[np.ndarray, np.ndarray, str]:
    """Return ``(scores, labels, name)`` for a domain's bundled reference."""
    if domain not in _REFERENCES:
        raise KeyError(domain)
    fname, name = _REFERENCES[domain]
    data = np.load(_DIR / fname)
    return data["scores"], data["labels"], name
