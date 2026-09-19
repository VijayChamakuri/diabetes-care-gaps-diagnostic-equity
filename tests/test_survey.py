import numpy as np
import pandas as pd
import pytest
from scipy import stats

from nhanes_diabetes.survey import (
    Design,
    SurveyError,
    contrast,
    degf,
    estimate_mean,
    holm_adjust,
    kish_effective_n,
    rao_wu_multipliers,
    standardized_proportion,
    variance,
)


def _frame() -> pd.DataFrame:
    # Two strata, two PSUs each, two respondents per PSU, unit weights.
    return pd.DataFrame({
        "stratum": [1] * 4 + [2] * 4,
        "psu": [1, 1, 2, 2, 1, 1, 2, 2],
        "weight": [1.0] * 8,
        "y": [1, 1, 0, 0, 1, 0, 0, 0],
    })


def test_known_answer_matches_hand_calculation() -> None:
    f = _frame()
    e = estimate_mean(Design.from_frame(f), f["y"])
    assert e.estimate == pytest.approx(3 / 8)
    # Scores u_i = (y_i - p) / 8. PSU totals: s1p1 = 2*(1-3/8)/8, s1p2 = 2*(-3/8)/8,
    # s2p1 = ((1-3/8) + (-3/8))/8, s2p2 = 2*(-3/8)/8. Variance = sum_h 2 * sum_j (t - mean)^2.
    t = np.array([2 * 5 / 8, 2 * -3 / 8, 1 * 5 / 8 + -3 / 8, 2 * -3 / 8]) / 8
    expected = 2 * ((t[0] - t[:2].mean()) ** 2 + (t[1] - t[:2].mean()) ** 2) + 2 * (
        (t[2] - t[2:].mean()) ** 2 + (t[3] - t[2:].mean()) ** 2)
    assert e.se == pytest.approx(np.sqrt(expected))
    assert e.df == 2  # 4 PSUs - 2 strata
    assert e.n == 8 and e.weighted_total == 8.0


def test_domain_estimation_keeps_the_full_design_for_variance() -> None:
    f = _frame()
    design = Design.from_frame(f)
    domain = (f["stratum"] == 1).to_numpy()
    e = estimate_mean(design, f["y"], domain)
    assert e.estimate == pytest.approx(0.5)
    assert e.df == 2 - 1 + 0  # 2 PSUs in the domain, 1 stratum
    # A subgroup analysed as its own survey drops the empty stratum and PSUs; the domain
    # estimator must not.
    alone = estimate_mean(Design.from_frame(f[f["stratum"] == 1]), f.loc[f["stratum"] == 1, "y"])
    assert alone.estimate == pytest.approx(e.estimate)
    assert alone.se == pytest.approx(e.se)  # equal here because stratum 2 has zero domain scores
    assert degf(design, domain) == 1


def test_logit_and_wald_intervals_use_t_on_domain_df() -> None:
    f = _frame()
    e = estimate_mean(Design.from_frame(f), f["y"])
    crit = stats.t.ppf(0.975, e.df)
    assert e.ci_wald[0] == pytest.approx(max(0.0, e.estimate - crit * e.se))
    centre = np.log(e.estimate / (1 - e.estimate))
    half = crit * e.se / (e.estimate * (1 - e.estimate))
    assert e.ci_logit[0] == pytest.approx(1 / (1 + np.exp(-(centre - half))))
    assert 0 < e.ci_logit[0] < e.estimate < e.ci_logit[1] < 1


def test_contrast_uses_covariance_not_independence() -> None:
    f = _frame()
    design = Design.from_frame(f)
    a = (np.arange(8) % 2 == 0)  # both domains sit inside every PSU, so their estimates covary
    b = ~a
    y = np.array([0, 0, 0, 0, 0, 0, 1, 1], dtype=float)
    c = contrast(design, y, a, b)
    ea, eb = estimate_mean(design, y, a), estimate_mean(design, y, b)
    assert ea.se > 0 and eb.se > 0
    assert c.difference == pytest.approx(ea.estimate - eb.estimate) == pytest.approx(0.0)
    # The two estimates move together, so the difference has no sampling variance here. Treating
    # them as independent would report hypot(se_a, se_b), which is wrong.
    assert c.se == pytest.approx(0.0, abs=1e-12)
    assert np.hypot(ea.se, eb.se) > 0.3
    d = np.array([1, 0, 1, 1, 1, 0, 0, 1], dtype=float)
    assert contrast(design, d, a, b).ratio == pytest.approx(
        estimate_mean(design, d, a).estimate / estimate_mean(design, d, b).estimate)


def test_invalid_weights_and_designs_fail_loudly() -> None:
    f = _frame()
    for bad, message in ((np.nan, "missing"), (-1.0, "negative")):
        g = f.copy()
        g.loc[0, "weight"] = bad
        with pytest.raises(SurveyError, match=message):
            Design.from_frame(g)
    g = f.copy()
    g["weight"] = 0.0
    with pytest.raises(SurveyError, match="positive"):
        Design.from_frame(g)
    with pytest.raises(SurveyError, match="lonely"):
        Design.from_frame(f, lonely="ignore")
    g = f.copy()
    g.loc[0, "psu"] = np.nan
    with pytest.raises(SurveyError, match="PSU"):
        Design.from_frame(g)


def test_zero_weights_are_excluded_not_errors() -> None:
    f = _frame()
    f.loc[0, "weight"] = 0.0
    e = estimate_mean(Design.from_frame(f), f["y"])
    assert e.n == 7 and e.weighted_total == 7.0


def test_lonely_psu_handling() -> None:
    f = _frame().iloc[:6].copy()  # stratum 2 now has one PSU with two rows... make it single PSU
    f.loc[f["stratum"] == 2, "psu"] = 1
    with pytest.raises(SurveyError, match="single PSU"):
        estimate_mean(Design.from_frame(f), f["y"])
    centered = estimate_mean(Design.from_frame(f, lonely="centered"), f["y"])
    removed = estimate_mean(Design.from_frame(f, lonely="remove"), f["y"])
    assert centered.se >= removed.se > 0


def test_single_class_and_empty_groups() -> None:
    f = _frame()
    design = Design.from_frame(f)
    none = estimate_mean(design, np.zeros(len(f)))
    assert none.estimate == 0 and none.se == 0
    assert np.isnan(none.ci_logit[0])  # logit interval is undefined at 0 or 1
    assert none.ci_wald == (0.0, 0.0)
    with pytest.raises(SurveyError, match="empty"):
        estimate_mean(design, f["y"], np.zeros(len(f), dtype=bool))
    with pytest.raises(SurveyError, match="missing"):
        estimate_mean(design, np.full(len(f), np.nan))


def test_kish_effective_n_and_standardization() -> None:
    assert kish_effective_n(np.ones(10)) == pytest.approx(10)
    assert kish_effective_n(np.array([1.0, 3.0])) == pytest.approx(16 / 10)
    f = _frame()
    design = Design.from_frame(f)
    bands = [(f["psu"] == 1).to_numpy().astype(float), (f["psu"] == 2).to_numpy().astype(float)]
    e = standardized_proportion(design, f["y"], np.ones(len(f)), bands, [0.5, 0.5])
    assert e.estimate == pytest.approx(0.5 * 0.5 + 0.5 * 0.25)
    with pytest.raises(SurveyError):
        standardized_proportion(design, f["y"], np.ones(len(f)), bands, [0.7, 0.7])


def test_holm_adjustment() -> None:
    assert holm_adjust([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm_adjust([0.5]) == [0.5]
    assert max(holm_adjust([0.4, 0.9])) <= 1.0


def test_rao_wu_bootstrap_is_reproducible_and_unbiased_for_the_variance() -> None:
    f = _frame()
    design = Design.from_frame(f)
    a = rao_wu_multipliers(design, np.random.default_rng(1), 400)
    b = rao_wu_multipliers(design, np.random.default_rng(1), 400)
    assert np.array_equal(a, b)
    # Two PSUs per stratum: exactly one is drawn and doubled, the other is dropped.
    assert set(np.unique(a)) == {0.0, 2.0}
    assert np.allclose(a.sum(axis=1), 4.0 * 1.0)  # multipliers keep the total per replicate
    assert a.mean() == pytest.approx(1.0, abs=0.05)
    # The bootstrap variance of the mean matches the linearized variance (naive resampling would not).
    w = f["weight"].to_numpy()
    y = f["y"].to_numpy(float)
    rows = a[:, design.cluster]
    means = (rows * w * y).sum(axis=1) / (rows * w).sum(axis=1)
    assert means.var() == pytest.approx(estimate_mean(design, y).se ** 2, rel=0.35)


def test_variance_of_zero_scores_is_zero() -> None:
    design = Design.from_frame(_frame())
    assert variance(design, np.zeros(design.n)) == 0.0
