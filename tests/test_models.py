import numpy as np
import pandas as pd

from nhanes_diabetes.metrics import weighted_auc
from nhanes_diabetes.models import ModelSpec, cross_validate, feature_frame, model_specs


def test_primary_models_exclude_race_and_never_use_hba1c() -> None:
    frame = pd.DataFrame({"age": [30.0, 50.0], "female": [0.0, 1.0], "bmi": [25.0, 30.0], "family_history": [1.0, 0.0],
                          "insured": [1.0, 1.0], "routine_care": [1.0, 0.0],
                          "race_label": ["Non-Hispanic White", "Non-Hispanic Black"]})
    groups = ["Non-Hispanic White", "Non-Hispanic Black", "Mexican American"]
    x, race = feature_frame(frame, groups)
    assert race == ["race_Non-Hispanic Black", "race_Mexican American"]  # reference group is the baseline
    specs = {s.name: s for s in model_specs(race)}
    for name in ("demographic_logistic", "extended_logistic", "extended_boosting"):
        assert not any(c.startswith("race_") for c in specs[name].columns)
    assert specs["demographic_race_logistic"].role == "sensitivity"
    assert all("hba1c" not in c for s in specs.values() for c in s.columns)
    assert set(x.columns) >= {c for s in specs.values() for c in s.columns}


def test_grouped_folds_stop_cluster_level_leakage() -> None:
    """A label fixed per cluster is learnable only if a cluster appears on both sides of a split."""
    rng = np.random.default_rng(0)
    clusters = np.repeat(np.arange(200), 6)
    label = rng.integers(0, 2, 200)[clusters].astype(float)
    x = pd.DataFrame({"age": clusters.astype(float)})  # the cluster id itself is the feature
    spec = ModelSpec("leak_probe", ("age",), "boosting", "comparison", "probe")
    cv = cross_validate(spec, x, label, np.ones(len(label)), clusters, label, folds=5, repeats=1,
                        inner_folds=2, seed=1)
    assert weighted_auc(label, cv.probability[0], np.ones(len(label))) < 0.6  # chance is 0.5; a cluster leak would push this toward 1


def test_cross_validation_gives_every_respondent_one_out_of_fold_prediction() -> None:
    rng = np.random.default_rng(2)
    n = 600
    clusters = rng.integers(0, 12, n)
    x = pd.DataFrame({"age": rng.normal(size=n), "female": rng.integers(0, 2, n).astype(float)})
    y = (x["age"] + rng.normal(size=n) > 0.5).astype(float).to_numpy()
    spec = ModelSpec("demographic_logistic", ("age", "female"), "logistic", "primary", "t")
    cv = cross_validate(spec, x, y, np.ones(n), clusters, y, folds=4, repeats=3, inner_folds=2, seed=5)
    assert cv.probability.shape == (3, n) and not np.isnan(cv.probability).any()
    assert cv.thresholds.shape == (3, 4) and np.isfinite(cv.thresholds).all()
    assert weighted_auc(y, cv.probability.mean(axis=0), np.ones(n)) > 0.7
    again = cross_validate(spec, x, y, np.ones(n), clusters, y, folds=4, repeats=3, inner_folds=2, seed=5)
    assert np.array_equal(cv.probability, again.probability)  # fixed seed, fixed answer
