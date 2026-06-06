"""Synthetic tests for Stage-A SSL: the masked autoencoder pretrains, and a
pretrained-then-fine-tuned embedder learns held-out same-source separation."""

import numpy as np
import pytest

pytest.importorskip("torch")

from verity.representation.mae import (  # noqa: E402
    ConvEncoder,
    MAEEmbedder,
    embed_mae,
    finetune_mae,
    pretrain_mae,
)


def _land(base_profile, rng, size=32):
    """A noisy, shifted view of a base across-striae profile as a 2-channel image."""
    from skimage.transform import resize

    w = len(base_profile)
    img = np.tile(base_profile, (size, 1))[:, :w]
    img = np.roll(img, int(rng.integers(-2, 3)), axis=1) + 0.3 * rng.standard_normal((size, w))
    img = resize(img, (size, size), order=1, mode="edge", anti_aliasing=False)
    img = (img - img.mean()) / (img.std() + 1e-9)
    return np.stack([img.astype(np.float32), np.ones((size, size), np.float32)])


def test_pretrain_mae_runs_and_returns_encoder():
    rng = np.random.default_rng(0)
    bases = [np.cumsum(rng.standard_normal(40)) * 0.2 for _ in range(12)]
    images = [_land(b, rng) for b in bases for _ in range(3)]  # 36 unlabeled lands
    encoder = pretrain_mae(images, epochs=20, seed=0)
    assert isinstance(encoder, ConvEncoder)
    # encoder produces a downsampled spatial feature map
    import torch

    feat = encoder(torch.from_numpy(np.stack(images[:2]).astype(np.float32)))
    assert feat.shape[0] == 2 and feat.ndim == 4


def test_pretrained_embedder_finetunes_to_separate_held_out():
    rng = np.random.default_rng(1)
    bases = [np.cumsum(rng.standard_normal(40)) * 0.2 for _ in range(24)]

    # Stage A: pretrain on ALL lands, unlabeled.
    all_imgs = [_land(b, rng) for b in bases for _ in range(3)]
    encoder = pretrain_mae(all_imgs, epochs=40, seed=0)

    # Stage B: fine-tune the metric head on labeled pairs from the first 16 bases.
    a, b, y = [], [], []
    for base in bases[:16]:
        a.append(_land(base, rng))
        b.append(_land(base, rng))
        y.append(1)
    for _ in range(48):
        i, j = rng.integers(0, 16, 2)
        if i != j:
            a.append(_land(bases[i], rng))
            b.append(_land(bases[j], rng))
            y.append(0)
    embedder = finetune_mae(MAEEmbedder(encoder), a, b, np.array(y), epochs=60, seed=0)

    km, knm = [], []
    for base in bases[16:]:  # held-out bases
        e = embed_mae(embedder, [_land(base, rng), _land(base, rng)])
        km.append(float(e[0] @ e[1]))
    for _ in range(40):
        i, j = rng.integers(16, 24, 2)
        if i != j:
            e = embed_mae(embedder, [_land(bases[i], rng), _land(bases[j], rng)])
            knm.append(float(e[0] @ e[1]))

    assert np.mean(km) > np.mean(knm) + 0.15
