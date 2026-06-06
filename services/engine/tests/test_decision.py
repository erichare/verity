import numpy as np

from verity import ScoreLRModel, cllr, cllr_min, ece, eer, roc_auc, tippett


def _labelled(km: np.ndarray, knm: np.ndarray):
    scores = np.concatenate([km, knm])
    labels = np.concatenate([np.ones(len(km)), np.zeros(len(knm))])
    return scores, labels


def test_separated_scores_are_informative():
    rng = np.random.default_rng(0)
    scores, labels = _labelled(rng.normal(5, 1, 500), rng.normal(-5, 1, 500))
    assert cllr_min(scores, labels) < 0.1
    assert roc_auc(scores, labels) > 0.99
    assert eer(scores, labels) < 0.02


def test_overlapping_scores_are_uninformative():
    rng = np.random.default_rng(1)
    scores, labels = _labelled(rng.normal(0, 1, 500), rng.normal(0, 1, 500))
    assert cllr_min(scores, labels) > 0.9
    assert abs(roc_auc(scores, labels) - 0.5) < 0.1


def test_score_lr_model_is_monotone_and_calibrated():
    rng = np.random.default_rng(2)
    scores, labels = _labelled(rng.normal(3, 1, 1000), rng.normal(0, 1, 1000))
    model = ScoreLRModel().fit(scores, labels)
    lr = model.predict_lr(scores)

    assert np.mean(lr[labels == 1]) > 1.0  # same-source -> LR > 1 on average
    assert np.mean(lr[labels == 0]) < 1.0
    order = np.argsort(scores)
    assert np.all(np.diff(model.predict_lr(scores[order])) >= -1e-9)  # monotone
    assert 0.0 < cllr(lr[labels == 1], lr[labels == 0]) < 1.0


def test_cllr_of_uninformative_system_is_one():
    assert abs(cllr(np.ones(100), np.ones(100)) - 1.0) < 1e-9


def test_ece_rewards_calibrated_lrs():
    # A perfectly reliable system: LR = 1 everywhere with a 50/50 split has
    # posterior 0.5 and empirical 0.5 -> ECE 0.
    assert ece(np.ones(100), np.ones(100)) < 1e-9
    # An over-confident system (huge LRs for KM, tiny for KNM, but only half
    # right) is miscalibrated -> ECE > 0.
    bad = ece(np.concatenate([np.full(50, 1e6), np.full(50, 1e-6)]), np.full(100, 1e6))
    assert bad > 0.1


def test_tippett_proportions_decrease_with_threshold():
    rng = np.random.default_rng(3)
    lr_km = np.exp(rng.normal(1, 1, 200))
    lr_knm = np.exp(rng.normal(-1, 1, 200))
    _, km_prop, knm_prop = tippett(lr_km, lr_knm)
    assert np.all(np.diff(km_prop) <= 1e-9)
    assert np.all(np.diff(knm_prop) <= 1e-9)
    assert km_prop[0] >= km_prop[-1]
