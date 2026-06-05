"""Synthetic tests: prove the learned-representation pipeline actually learns
(on data where signal definitely exists) before it touches real scans."""

import numpy as np
import pytest

pytest.importorskip("torch")
from scipy.ndimage import gaussian_filter1d  # noqa: E402

from verity.representation import SignatureEncoder, embed, prepare, train_encoder  # noqa: E402


def _smooth(rng, length=400):
    return gaussian_filter1d(rng.standard_normal(length), 4)


def _view(base, rng):
    """A noisy, shifted view of a base profile — a synthetic 'same-source' scan."""
    return np.roll(base, int(rng.integers(-20, 20))) + 0.2 * rng.standard_normal(len(base))


def test_prepare_is_fixed_length_and_normalized():
    x = prepare([np.arange(300.0), np.arange(500.0)], length=256)
    assert x.shape == (2, 256)
    assert abs(x[0].mean()) < 1e-4 and abs(x[0].std() - 1.0) < 1e-3


def test_encoder_is_shift_invariant_by_construction():
    rng = np.random.default_rng(0)
    base = _smooth(rng)
    e = embed(SignatureEncoder(), [base, np.roll(base, 17)])
    assert float(np.dot(e[0], e[1])) > 0.8  # untrained, via global pooling


def test_training_separates_held_out_synthetic():
    rng = np.random.default_rng(1)
    bases = [_smooth(rng) for _ in range(40)]

    a, b, y = [], [], []
    for base in bases[:30]:  # positives: two views of the same base
        a.append(_view(base, rng))
        b.append(_view(base, rng))
        y.append(1)
    for _ in range(90):  # negatives: views of different bases
        i, j = rng.integers(0, 30, 2)
        if i != j:
            a.append(_view(bases[i], rng))
            b.append(_view(bases[j], rng))
            y.append(0)

    encoder = train_encoder(a, b, np.array(y), epochs=60, seed=0)

    # Held-out bases (30:40) never seen in training.
    km = [
        (embed(encoder, [_view(base, rng)])[0], embed(encoder, [_view(base, rng)])[0])
        for base in bases[30:]
    ]
    km_cos = np.array([float(np.dot(x, z)) for x, z in km])
    knm_cos = []
    for _ in range(40):
        i, j = rng.integers(30, 40, 2)
        if i != j:
            ea = embed(encoder, [_view(bases[i], rng)])[0]
            eb = embed(encoder, [_view(bases[j], rng)])[0]
            knm_cos.append(float(np.dot(ea, eb)))
    knm_cos = np.array(knm_cos)

    assert km_cos.mean() > knm_cos.mean() + 0.2  # learned similarity generalizes
