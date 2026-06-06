"""The learned representation: a small encoder whose cosine similarity is a
drop-in score for the decision layer. Phase 2b is a 1-D signature encoder; Phase
2 adds a 2-D land-surface encoder (the real representation). Requires the
``learn`` extra (PyTorch)."""

from .encoder import SignatureEncoder, embed, prepare, train_encoder
from .labels import best_rotation, bootstrap_pairs
from .surface_encoder import SurfaceEncoder, embed_surfaces, stack_images, train_surface_encoder
from .surface_image import land_image

__all__ = [
    "SignatureEncoder",
    "train_encoder",
    "embed",
    "prepare",
    "best_rotation",
    "bootstrap_pairs",
    "SurfaceEncoder",
    "train_surface_encoder",
    "embed_surfaces",
    "stack_images",
    "land_image",
]
