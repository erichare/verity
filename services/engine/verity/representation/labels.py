"""Bootstrap same-source land-pair labels from the Phase-1 matcher.

Same-barrel bullets share the rifling, but *which land matches which* (the groove
correspondence) is unlabelled — so we take it from the best-aligned diagonal of
the cross-correlation matrix. Different-barrel land pairs are negatives.

We are explicit about the mild circularity: the encoder is bootstrapped from the
CCF's own correspondences, so it can only *re-rank* what CCF already aligns — but
it may learn richer, more transferable features. Proper same-source labels (or
much more data) would remove the circularity.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np

from ..registration import align_1d


def best_rotation(sigs_a, sigs_b) -> int:
    """Cyclic land offset maximizing the mean diagonal cross-correlation."""
    m = len(sigs_b)
    ccf = np.array([[align_1d(x, y)[1] for y in sigs_b] for x in sigs_a])
    n = ccf.shape[0]
    return int(max(range(m), key=lambda k: np.mean([ccf[i, (i + k) % m] for i in range(n)])))


def bootstrap_pairs(bullets, *, neg_ratio: int = 4, seed: int = 0):
    """From ``[(barrel, key, signatures)]`` build ``(sigs_a, sigs_b, labels)``:
    same-source positives along each same-barrel bullet pair's best diagonal, and
    a sampled set of different-barrel negatives."""
    rng = np.random.default_rng(seed)
    sigs_a, sigs_b, labels = [], [], []
    negatives = []
    for (ba, _ka, sa), (bb, _kb, sb) in combinations(bullets, 2):
        if ba == bb:
            offset = best_rotation(sa, sb)
            m = len(sb)
            for i in range(len(sa)):
                sigs_a.append(sa[i])
                sigs_b.append(sb[(i + offset) % m])
                labels.append(1)
        else:
            for i in range(min(len(sa), len(sb))):
                negatives.append((sa[i], sb[i]))

    n_neg = neg_ratio * sum(labels)
    if len(negatives) > n_neg:
        negatives = [negatives[i] for i in rng.choice(len(negatives), n_neg, replace=False)]
    for a, b in negatives:
        sigs_a.append(a)
        sigs_b.append(b)
        labels.append(0)
    return sigs_a, sigs_b, np.array(labels)
