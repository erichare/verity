"""A small 2-D CNN over the orientation-normalized land image → L2-normalized
embedding. Cosine similarity of two embeddings is a drop-in *score* for the
decision layer — the learned analogue of the 2-D surface cross-correlation,
replacing the Phase-2b encoder that only saw the collapsed 1-D signature.

Augmentations encode the post-orientation invariances: striae run vertically, so
along-striae (vertical) translation and flip are identity-preserving, while the
across-striae (horizontal) direction carries the individualizing pattern and so
gets only small jitter. Requires the ``learn`` extra (PyTorch).
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn


def stack_images(images) -> torch.Tensor:
    """List of ``(2, H, W)`` arrays → a ``(N, 2, H, W)`` float32 tensor."""
    return torch.from_numpy(np.stack(images).astype(np.float32))


class SurfaceEncoder(nn.Module):
    """2-D CNN → L2-normalized embedding. Global pooling for shift-tolerance."""

    def __init__(self, emb_dim: int = 64):
        super().__init__()

        def block(ci: int, co: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv2d(ci, co, 3, padding=1),
                nn.BatchNorm2d(co),
                nn.ReLU(),
                nn.MaxPool2d(2),
            )

        self.features = nn.Sequential(
            block(2, 16), block(16, 32), block(32, 64), nn.AdaptiveAvgPool2d(1)
        )
        self.head = nn.Linear(64, emb_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.features(x).flatten(1)
        return nn.functional.normalize(self.head(h), dim=-1)


def _augment(x: torch.Tensor, gen: torch.Generator) -> torch.Tensor:
    """Random along-striae (vertical) roll + flip, small across-striae jitter."""
    h = x.shape[2]
    x = torch.roll(x, int(torch.randint(0, h, (1,), generator=gen)), dims=2)
    x = torch.roll(x, int(torch.randint(-3, 4, (1,), generator=gen)), dims=3)
    if torch.rand(1, generator=gen) < 0.5:
        x = torch.flip(x, dims=[2])
    return x


def train_surface_encoder(
    images_a,
    images_b,
    labels,
    *,
    emb_dim: int = 64,
    epochs: int = 60,
    lr: float = 1e-3,
    augment: bool = True,
    seed: int = 0,
) -> SurfaceEncoder:
    """Train so the cosine similarity of paired land-image embeddings separates
    same-source (label 1) from different-source (label 0)."""
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    a = stack_images(images_a)
    b = stack_images(images_b)
    y = torch.from_numpy(np.asarray(labels, dtype=np.float32))

    encoder = SurfaceEncoder(emb_dim)
    scale = nn.Parameter(torch.tensor(5.0))
    bias = nn.Parameter(torch.tensor(0.0))
    optim = torch.optim.Adam([*encoder.parameters(), scale, bias], lr=lr)
    pos_weight = torch.tensor([(y == 0).sum() / max((y == 1).sum(), 1)])
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    encoder.train()
    for _ in range(epochs):
        ea = encoder(_augment(a, gen) if augment else a)
        eb = encoder(_augment(b, gen) if augment else b)
        cos = (ea * eb).sum(-1)
        optim.zero_grad()
        loss_fn(scale * cos + bias, y).backward()
        optim.step()
    encoder.eval()
    return encoder


@torch.no_grad()
def embed_surfaces(encoder: SurfaceEncoder, images) -> np.ndarray:
    """L2-normalized embeddings ``(N, emb_dim)`` for a list of land images."""
    encoder.eval()
    return encoder(stack_images(images)).numpy()
