"""Synthetic tests for the Phase-2 2-D land representation: prove the surface
encoder learns held-out same-source separation on data where signal exists,
before it touches real scans."""

import numpy as np
import pytest

pytest.importorskip("torch")

from verity.representation.surface_encoder import (  # noqa: E402
    embed_surfaces,
    train_surface_encoder,
)
from verity.representation.surface_image import land_image  # noqa: E402
from verity.surface import Surface  # noqa: E402


def _striae_surface(rng, ny=80, nx=120):
    """A land-like surface: vertical striae (a 1-D across-striae profile broadcast
    down the rows) plus form + noise."""
    profile = np.cumsum(rng.standard_normal(nx)) * 0.1
    z = np.tile(profile, (ny, 1)) + 0.05 * rng.standard_normal((ny, nx))
    z += np.linspace(0, 1, ny)[:, None] * 2.0  # a tilt (form) to be removed
    return Surface(heights=z, dx=1e-6, dy=1e-6)


def _land(base_profile, rng, size=32):
    """A noisy, shifted view of a base across-striae profile as a 2-channel image."""
    w = len(base_profile)
    img = np.tile(base_profile, (size, 1))[:, :w]
    img = np.roll(img, int(rng.integers(-2, 3)), axis=1) + 0.3 * rng.standard_normal((size, w))
    from skimage.transform import resize

    img = resize(img, (size, size), order=1, mode="edge", anti_aliasing=False)
    img = (img - img.mean()) / (img.std() + 1e-9)
    return np.stack([img.astype(np.float32), np.ones((size, size), np.float32)])


def test_land_image_shape_and_norm():
    rng = np.random.default_rng(0)
    img = land_image(_striae_surface(rng), size=48, orient=False)
    assert img.shape == (2, 48, 48)
    assert set(np.unique(img[1])).issubset({0.0, 1.0})  # mask is binary
    vals = img[0][img[1] > 0]
    assert np.isfinite(vals).all()
    assert abs(vals.std() - 1.0) < 0.2  # roughly unit-scaled on the valid region


def test_land_image_orientation_runs():
    rng = np.random.default_rng(1)
    img = land_image(_striae_surface(rng), lambda_s=4e-6, lambda_c=250e-6, size=32, orient=True)
    assert img.shape == (2, 32, 32)
    assert np.isfinite(img).all()


def test_surface_training_separates_held_out_synthetic():
    rng = np.random.default_rng(2)
    bases = [np.cumsum(rng.standard_normal(40)) * 0.2 for _ in range(24)]

    a, b, y = [], [], []
    for base in bases[:16]:  # positives: two views of one base
        a.append(_land(base, rng))
        b.append(_land(base, rng))
        y.append(1)
    for _ in range(48):  # negatives: views of different bases
        i, j = rng.integers(0, 16, 2)
        if i != j:
            a.append(_land(bases[i], rng))
            b.append(_land(bases[j], rng))
            y.append(0)

    encoder = train_surface_encoder(a, b, np.array(y), epochs=80, seed=0)

    km = []
    for base in bases[16:]:  # held-out bases, never trained on
        e = embed_surfaces(encoder, [_land(base, rng), _land(base, rng)])
        km.append(float(e[0] @ e[1]))
    knm = []
    for _ in range(40):
        i, j = rng.integers(16, 24, 2)
        if i != j:
            e = embed_surfaces(encoder, [_land(bases[i], rng), _land(bases[j], rng)])
            knm.append(float(e[0] @ e[1]))

    assert np.mean(km) > np.mean(knm) + 0.15  # learned similarity generalizes
