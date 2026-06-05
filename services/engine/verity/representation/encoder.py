"""A small shift-invariant 1-D encoder for striation signatures, with a
contrastive training loop.

The encoder maps a signature to an L2-normalized embedding; the cosine
similarity of two embeddings is a drop-in *score* for the decision layer
(replacing the hand-engineered cross-correlation). Global average pooling makes
the embedding approximately shift-invariant, so two misaligned same-source
signatures still embed close — the learned analogue of cross-correlation's
search over lag.

Requires the ``learn`` extra (PyTorch).
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

DEFAULT_LENGTH = 512


def _prep_one(sig: np.ndarray, length: int) -> np.ndarray:
    """Interp-fill NaNs, resample to fixed length, mean-center, unit-scale."""
    sig = np.asarray(sig, dtype=np.float64)
    idx = np.arange(len(sig))
    good = ~np.isnan(sig)
    if good.sum() < 2:
        return np.zeros(length, dtype=np.float32)
    sig = np.interp(idx, idx[good], sig[good])
    resampled = np.interp(np.linspace(0, len(sig) - 1, length), idx, sig)
    resampled = resampled - resampled.mean()
    std = resampled.std()
    if std > 0:
        resampled = resampled / std
    return resampled.astype(np.float32)


def prepare(signatures, length: int = DEFAULT_LENGTH) -> np.ndarray:
    """Stack signatures into a fixed-length, normalized ``(N, length)`` array."""
    return np.stack([_prep_one(s, length) for s in signatures])


class SignatureEncoder(nn.Module):
    """1-D CNN → L2-normalized embedding. Shift-invariant via global pooling."""

    def __init__(self, emb_dim: int = 64):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=9, padding=4),
            nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=9, padding=4),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(32, 64, kernel_size=9, padding=4),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Linear(64, emb_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.features(x.unsqueeze(1)).squeeze(-1)
        return nn.functional.normalize(self.head(h), dim=-1)


def train_encoder(
    sigs_a,
    sigs_b,
    labels,
    *,
    length: int = DEFAULT_LENGTH,
    emb_dim: int = 64,
    epochs: int = 40,
    lr: float = 1e-3,
    seed: int = 0,
) -> SignatureEncoder:
    """Train the encoder so the cosine similarity of paired embeddings separates
    same-source (label 1) from different-source (label 0) signatures."""
    torch.manual_seed(seed)
    a = torch.from_numpy(prepare(sigs_a, length))
    b = torch.from_numpy(prepare(sigs_b, length))
    y = torch.from_numpy(np.asarray(labels, dtype=np.float32))

    encoder = SignatureEncoder(emb_dim)
    scale = nn.Parameter(torch.tensor(5.0))
    bias = nn.Parameter(torch.tensor(0.0))
    optim = torch.optim.Adam([*encoder.parameters(), scale, bias], lr=lr)
    # Balance the classes so the equal-prior objective isn't swamped by negatives.
    pos_weight = torch.tensor([(y == 0).sum() / max((y == 1).sum(), 1)])
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    encoder.train()
    for _ in range(epochs):
        optim.zero_grad()
        cos = (encoder(a) * encoder(b)).sum(-1)
        loss_fn(scale * cos + bias, y).backward()
        optim.step()
    encoder.eval()
    return encoder


@torch.no_grad()
def embed(encoder: SignatureEncoder, signatures, length: int = DEFAULT_LENGTH) -> np.ndarray:
    """L2-normalized embeddings ``(N, emb_dim)`` for a list of signatures."""
    x = torch.from_numpy(prepare(signatures, length))
    return encoder(x).numpy()
