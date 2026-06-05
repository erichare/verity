"""The learned representation (Phase 2b): a small shift-invariant encoder whose
cosine similarity is a drop-in score for the decision layer. Requires the
``learn`` extra (PyTorch)."""

from .encoder import SignatureEncoder, embed, prepare, train_encoder
from .labels import best_rotation, bootstrap_pairs

__all__ = [
    "SignatureEncoder",
    "train_encoder",
    "embed",
    "prepare",
    "best_rotation",
    "bootstrap_pairs",
]
