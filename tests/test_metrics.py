import numpy as np
import pytest

from nhanes_diabetes.metrics import (
    calibration_bins,
    confusion_sums,
    rates,
    weighted_auc,
    weighted_brier,
    youden_threshold,
)


def test_youden_threshold_picks_the_separating_cut() -> None:
    y = np.array([0, 0, 0, 1, 1, 1], dtype=float)
    p = np.array([0.1, 0.2, 0.3, 0.6, 0.7, 0.9])
    assert youden_threshold(y, p, np.ones(6)) == pytest.approx(0.6)


def test_youden_respects_weights_and_handles_one_class() -> None:
    y = np.array([0, 0, 1, 1], dtype=float)
    p = np.array([0.2, 0.6, 0.5, 0.9])
    heavy = youden_threshold(y, p, np.array([1.0, 100.0, 1.0, 1.0]))
    assert heavy > 0.6  # the heavily weighted negative at 0.6 must fall below the threshold
    assert youden_threshold(np.ones(4), p, np.ones(4)) == 0.5


def test_weighted_confusion_and_rates_for_many_weight_vectors() -> None:
    y = np.array([1, 1, 0, 0, 1], dtype=float)
    pred = np.array([1, 0, 0, 1, 1], dtype=float)
    w = np.array([[1.0, 1, 1, 1, 1], [2.0, 2, 2, 2, 2]])
    tp, fn, tn, fp = confusion_sums(y, pred, w)
    assert tp.tolist() == [2, 4] and fn.tolist() == [1, 2] and tn.tolist() == [1, 2] and fp.tolist() == [1, 2]
    r = rates(tp, fn, tn, fp)
    assert r["sensitivity"].tolist() == pytest.approx([2 / 3, 2 / 3])
    assert r["specificity"][0] == pytest.approx(0.5)
    assert r["ppv"][0] == pytest.approx(2 / 3) and r["npv"][0] == pytest.approx(0.5)


def test_rates_are_nan_not_zero_when_a_denominator_is_empty() -> None:
    r = rates(np.array(0.0), np.array(0.0), np.array(3.0), np.array(1.0))
    assert np.isnan(r["sensitivity"]) and r["specificity"] == pytest.approx(0.75)


def test_mask_restricts_the_confusion_counts() -> None:
    y = np.array([1, 0, 1, 0], dtype=float)
    pred = np.array([1, 0, 0, 1], dtype=float)
    tp, fn, tn, fp = confusion_sums(y, pred, np.ones(4), np.array([True, True, False, False]))
    assert (tp, fn, tn, fp) == (1, 0, 1, 0)


def test_auc_brier_and_calibration() -> None:
    y = np.array([0, 0, 1, 1], dtype=float)
    p = np.array([0.1, 0.4, 0.35, 0.8])
    assert weighted_auc(y, p, np.ones(4)) == pytest.approx(0.75)
    assert np.isnan(weighted_auc(np.zeros(4), p, np.ones(4)))
    assert weighted_brier(y, p, np.ones(4)) == pytest.approx(np.mean((p - y) ** 2))
    bins = calibration_bins(y, p, np.ones(4), bins=2)
    assert [b["n"] for b in bins] == [2, 2]
    # Sorted by risk: (0.1, y=0), (0.35, y=1) | (0.4, y=0), (0.8, y=1)
    assert bins[0]["mean_predicted"] == pytest.approx(0.225) and bins[0]["observed_rate"] == pytest.approx(0.5)
    assert bins[1]["mean_predicted"] == pytest.approx(0.6) and bins[1]["observed_rate"] == pytest.approx(0.5)
