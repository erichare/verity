import numpy as np

from verity import ScoreLRModel, cllr, cllr_min, ece, eer, roc_auc, tippett
from verity.decision import lr_separation, margin


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


def test_lr_bound_caps_overconfident_lrs():
    # Hugely separated classes: an unbounded near-unregularized logistic emits
    # extreme LRs. The data-driven "auto" bound caps |log10 LR| at log10(n_min).
    rng = np.random.default_rng(7)
    scores, labels = _labelled(rng.normal(8, 1, 50), rng.normal(-8, 1, 50))  # n_min = 50
    cap = 10.0 ** np.log10(50)  # ~= 50

    bounded = ScoreLRModel(lr_bound="auto").fit(scores, labels).predict_lr(scores)
    unbounded = ScoreLRModel(lr_bound=None).fit(scores, labels).predict_lr(scores)

    assert bounded.max() <= cap + 1e-6
    assert bounded.min() >= 1.0 / cap - 1e-9
    assert unbounded.max() > 100.0  # unbounded really is over-confident here

    # A fixed bound is honored, and bounding preserves monotonicity.
    fixed = ScoreLRModel(lr_bound=1.0).fit(scores, labels)
    order = np.argsort(scores)
    lr_sorted = fixed.predict_lr(scores[order])
    assert lr_sorted.max() <= 10.0 + 1e-6  # |log10 LR| <= 1
    assert np.all(np.diff(lr_sorted) >= -1e-9)


def test_predict_lr_flags_exactly_the_bound_hits():
    rng = np.random.default_rng(7)
    scores, labels = _labelled(rng.normal(8, 1, 50), rng.normal(-8, 1, 50))  # n_min = 50
    cap = 10.0 ** np.log10(50)

    bounded = ScoreLRModel(lr_bound="auto").fit(scores, labels)
    lr, hit = bounded.predict_lr(scores, return_bound_hit=True)
    assert hit.dtype == bool and hit.any()  # extreme scores really are clipped

    # exactly the scores whose pre-cap LR exceeded the bound are flagged, in
    # either direction (an identically-fitted unbounded model gives the pre-cap LR)
    pre_cap = ScoreLRModel(lr_bound=None).fit(scores, labels).predict_lr(scores)
    np.testing.assert_array_equal(hit, (pre_cap > cap) | (pre_cap < 1.0 / cap))

    # no bound -> nothing can be flagged
    _, no_hit = (
        ScoreLRModel(lr_bound=None).fit(scores, labels).predict_lr(scores, return_bound_hit=True)
    )
    assert not no_hit.any()


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


def test_margin_wider_for_separated_scores():
    rng = np.random.default_rng(4)
    sep_s, sep_l = _labelled(rng.normal(5, 1, 500), rng.normal(-5, 1, 500))
    ovl_s, ovl_l = _labelled(rng.normal(0.2, 1, 500), rng.normal(0, 1, 500))
    sep, ovl = margin(sep_s, sep_l), margin(ovl_s, ovl_l)
    assert sep["cohens_d"] > ovl["cohens_d"]
    assert sep["pct_gap"] > ovl["pct_gap"]
    assert sep["pct_gap"] > 0 > ovl["pct_gap"]  # clean gap vs interleaved tails


def test_lr_separation_signed_by_evidence_direction():
    assert lr_separation(np.full(50, 100.0), np.full(50, 0.01)) > 0
    assert lr_separation(np.full(50, 0.01), np.full(50, 100.0)) < 0


def test_tippett_proportions_decrease_with_threshold():
    rng = np.random.default_rng(3)
    lr_km = np.exp(rng.normal(1, 1, 200))
    lr_knm = np.exp(rng.normal(-1, 1, 200))
    _, km_prop, knm_prop = tippett(lr_km, lr_knm)
    assert np.all(np.diff(km_prop) <= 1e-9)
    assert np.all(np.diff(knm_prop) <= 1e-9)
    assert km_prop[0] >= km_prop[-1]
