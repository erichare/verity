"""The single source of truth for the comparison scorer's hyperparameters.

Drift between the thresholds the deployed code scores with and the thresholds a bundled
reference was *generated* under silently invalidates the likelihood ratio: the query
score and the calibration would live on different scales, so the LR would be a number
with no meaning. This module makes that configuration explicit, hashable, and
serializable, so every reference records the exact config it was built under and the
server can detect — and, in release mode, refuse — a mismatch.
"""

from __future__ import annotations

import hashlib
import json
import os
import warnings
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScorerConfig:
    """Immutable scorer hyperparameters. The defaults are the deployed values."""

    # Striated roughness band (m): ISO 16610 short/long wavelength cutoffs.
    lambda_s: float = 4e-6
    lambda_c: float = 250e-6
    # 2-D CMR (impressed) congruence thresholds: correlation floor + (dx, dy, dθ) tol.
    cmr_corr: float = 0.3
    cmr_tol: tuple[float, float, float] = (20.0, 20.0, 6.0)
    # 1-D striae-band congruence (striated attribution): correlation floor + lag tol.
    cmr_1d_corr: float = 0.5
    cmr_1d_lag: float = 10.0
    # Bullet scorer identity — the calibration reference must be scored the same way.
    name: str = "bullet-contrast"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["cmr_tol"] = list(self.cmr_tol)  # JSON has no tuples
        return d

    @classmethod
    def from_overrides(cls, overrides: dict) -> ScorerConfig:
        """Build a config from a dict of overrides on top of the deployed default.

        Unknown keys raise ``ValueError``; the ``cmr_tol`` list is coerced to a
        tuple (JSON has no tuples), and the band ordering
        (``lambda_s < lambda_c``) is enforced — so HTTP and in-process (MCP)
        callers share one validator. A ``None`` or empty dict returns the default
        unchanged."""
        if not overrides:
            return DEFAULT_SCORER_CONFIG
        if not isinstance(overrides, dict):
            raise ValueError("scorer_config must be a JSON object")
        known = set(asdict(DEFAULT_SCORER_CONFIG))
        unknown = set(overrides) - known
        if unknown:
            raise ValueError(f"unknown scorer_config keys: {sorted(unknown)}")
        merged = {**DEFAULT_SCORER_CONFIG.to_dict(), **overrides}
        merged["cmr_tol"] = tuple(merged["cmr_tol"])
        try:
            cfg = cls(**merged)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid scorer_config: {exc}") from exc
        if not cfg.lambda_s < cfg.lambda_c:
            raise ValueError("scorer_config requires lambda_s < lambda_c")
        return cfg

    @property
    def config_hash(self) -> str:
        """A stable content hash (sha256 of canonical JSON) identifying this config."""
        payload = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


DEFAULT_SCORER_CONFIG = ScorerConfig()


class ScorerConfigDrift(RuntimeError):
    """The running scorer config disagrees with a reference's recorded config."""


def _strict() -> bool:
    return os.environ.get("VERITY_STRICT_REFERENCE", "").strip().lower() in ("1", "true", "yes")


def check_scorer_drift(
    recorded_hash: str | None,
    *,
    reference_name: str,
    config: ScorerConfig | None = None,
) -> bool:
    """Compare a reference's recorded scorer-config hash to the running one.

    Returns ``True`` when consistent (or unverifiable). A legacy reference with no
    recorded hash is exempt — there is nothing to compare. A genuine mismatch warns by
    default and raises :class:`ScorerConfigDrift` under ``VERITY_STRICT_REFERENCE=1``
    (release gating), so a stale reference can never silently ship a mis-scaled LR."""
    cfg = config or DEFAULT_SCORER_CONFIG
    if not recorded_hash or recorded_hash == cfg.config_hash:
        return True
    msg = (
        f"scorer-config drift for reference {reference_name!r}: it was built under config "
        f"{recorded_hash[:12]} but the running engine uses {cfg.config_hash[:12]}; the "
        "calibration may not match the query score's scale — regenerate the reference."
    )
    if _strict():
        raise ScorerConfigDrift(msg)
    warnings.warn(msg, stacklevel=2)
    return False
