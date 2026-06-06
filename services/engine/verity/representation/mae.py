"""Stage-A self-supervised pretraining — a convolutional masked autoencoder over
the 2-D land surfaces.

The supervised 2-D encoder is data-limited (~200 labeled scans/study). MAE is the
data-efficiency backbone: it pretrains the *shared* conv encoder on ALL surfaces
*unlabeled* (pooled across studies) by masking random patches of the land image
and reconstructing them, learning individualizing surface texture before any
same-source labels are used. The pretrained encoder is then fine-tuned with a
thin metric head (see :mod:`verity.examples.ssl_learned`).

Requires the ``learn`` extra (PyTorch).
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from .surface_encoder import stack_images


class ConvEncoder(nn.Module):
    """``(B, 2, S, S)`` → ``(B, ch, S/8, S/8)`` spatial features (3 stride-2 blocks)."""

    def __init__(self, ch: int = 64):
        super().__init__()

        def block(ci: int, co: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv2d(ci, co, 3, stride=2, padding=1), nn.BatchNorm2d(co), nn.ReLU()
            )

        self.net = nn.Sequential(block(2, ch // 4), block(ch // 4, ch // 2), block(ch // 2, ch))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class ConvDecoder(nn.Module):
    """``(B, ch, S/8, S/8)`` → ``(B, 2, S, S)`` reconstruction (3 stride-2 up-blocks)."""

    def __init__(self, ch: int = 64):
        super().__init__()

        def up(ci: int, co: int, last: bool = False) -> nn.Sequential:
            layers = [nn.ConvTranspose2d(ci, co, 4, stride=2, padding=1)]
            if not last:
                layers += [nn.BatchNorm2d(co), nn.ReLU()]
            return nn.Sequential(*layers)

        self.net = nn.Sequential(
            up(ch, ch // 2), up(ch // 2, ch // 4), up(ch // 4, 2, last=True)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def _random_patch_mask(n: int, size: int, patch: int, ratio: float, gen: torch.Generator):
    """``(n, 1, size, size)`` mask, 1 where a patch is *kept*, 0 where masked."""
    grid = size // patch
    keep = (torch.rand(n, 1, grid, grid, generator=gen) > ratio).float()
    return keep.repeat_interleave(patch, 2).repeat_interleave(patch, 3)


def pretrain_mae(
    images,
    *,
    ch: int = 64,
    epochs: int = 150,
    lr: float = 1e-3,
    patch: int = 8,
    mask_ratio: float = 0.6,
    seed: int = 0,
) -> ConvEncoder:
    """Pretrain the conv encoder by masked reconstruction of the height channel
    (loss on masked, *valid* pixels). Returns the trained encoder."""
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    x = stack_images(images)  # (N, 2, S, S): [height, validity mask]
    size = x.shape[-1]

    encoder = ConvEncoder(ch)
    decoder = ConvDecoder(ch)
    optim = torch.optim.Adam([*encoder.parameters(), *decoder.parameters()], lr=lr)

    encoder.train()
    decoder.train()
    for _ in range(epochs):
        keep = _random_patch_mask(x.shape[0], size, patch, mask_ratio, gen)
        masked = x.clone()
        masked[:, 0:1] = masked[:, 0:1] * keep  # hide the height in masked patches
        recon = decoder(encoder(masked))
        valid = x[:, 1:2]
        target_mask = (1.0 - keep) * valid  # reconstruct masked AND measured pixels
        denom = target_mask.sum().clamp_min(1.0)
        loss = (((recon[:, 0:1] - x[:, 0:1]) ** 2) * target_mask).sum() / denom
        optim.zero_grad()
        loss.backward()
        optim.step()
    encoder.eval()
    return encoder


class MAEEmbedder(nn.Module):
    """Pretrained encoder + global pool + projection → L2-normalized embedding."""

    def __init__(self, encoder: ConvEncoder, ch: int = 64, emb_dim: int = 64):
        super().__init__()
        self.encoder = encoder
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(ch, emb_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.pool(self.encoder(x)).flatten(1)
        return nn.functional.normalize(self.head(h), dim=-1)


def finetune_mae(
    embedder: MAEEmbedder,
    images_a,
    images_b,
    labels,
    *,
    epochs: int = 40,
    lr: float = 1e-3,
    augment: bool = True,
    freeze_encoder: bool = False,
    seed: int = 0,
) -> MAEEmbedder:
    """Fine-tune the pretrained embedder so paired-embedding cosine separates
    same-source (1) from different-source (0). ``freeze_encoder`` makes it a
    linear probe of the SSL features."""
    from .surface_encoder import _augment

    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)
    a, b = stack_images(images_a), stack_images(images_b)
    y = torch.from_numpy(np.asarray(labels, dtype=np.float32))

    if freeze_encoder:
        for p in embedder.encoder.parameters():
            p.requires_grad = False
    scale = nn.Parameter(torch.tensor(5.0))
    bias = nn.Parameter(torch.tensor(0.0))
    params = [p for p in embedder.parameters() if p.requires_grad] + [scale, bias]
    optim = torch.optim.Adam(params, lr=lr)
    pos_weight = torch.tensor([(y == 0).sum() / max((y == 1).sum(), 1)])
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    embedder.train()
    for _ in range(epochs):
        ea = embedder(_augment(a, gen) if augment else a)
        eb = embedder(_augment(b, gen) if augment else b)
        cos = (ea * eb).sum(-1)
        optim.zero_grad()
        loss_fn(scale * cos + bias, y).backward()
        optim.step()
    embedder.eval()
    return embedder


@torch.no_grad()
def embed_mae(embedder: MAEEmbedder, images) -> np.ndarray:
    embedder.eval()
    return embedder(stack_images(images)).numpy()
