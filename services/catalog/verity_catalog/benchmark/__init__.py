"""The open benchmark: frozen split loading, submission scoring, and the
replication kit. Splits are produced by the engine's ``verity-build-benchmark``
and loaded verbatim (``verity-catalog load-benchmark <dir>``)."""

from .io import SplitArtifacts, read_split_dir
from .scoring import score_submission, validate_lrs

__all__ = ["SplitArtifacts", "read_split_dir", "score_submission", "validate_lrs"]
