"""Model specifications and design-aware repeated cross-validation.

Two labels are compared on identical features: ``diagnosed`` (a doctor told the respondent) and
``hba1c_pos`` (HbA1c at or above the ADA cut-off). HbA1c is never a feature. Race is excluded from
the primary specifications; race-included versions are sensitivity analyses because using race as
a predictor while auditing performance by race needs explicit justification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from nhanes_diabetes.metrics import youden_threshold

REFERENCE_RACE = "Non-Hispanic White"
LABELS = {"diagnosed": "M1 diagnosed label", "hba1c_pos": "M2 HbA1c criterion"}


@dataclass(frozen=True)
class ModelSpec:
    name: str
    columns: tuple[str, ...]
    algorithm: str  # logistic | boosting
    role: str  # primary | sensitivity | comparison
    description: str


DEMOGRAPHIC = ("age", "female")
CLINICAL = ("age", "female", "bmi", "family_history", "insured", "routine_care")


def model_specs(race_columns: list[str]) -> list[ModelSpec]:
    race = tuple(race_columns)
    return [
        ModelSpec("demographic_logistic", DEMOGRAPHIC, "logistic", "primary",
                  "Age and sex, race excluded (primary benchmark)"),
        ModelSpec("demographic_race_logistic", DEMOGRAPHIC + race, "logistic", "sensitivity",
                  "Age, sex and race dummies (sensitivity)"),
        ModelSpec("extended_logistic", CLINICAL, "logistic", "sensitivity",
                  "Adds BMI, family history, insurance and a routine care place; race excluded"),
        ModelSpec("extended_boosting", CLINICAL, "boosting", "comparison",
                  "Gradient boosting on the extended features, to test whether nonlinearity adds value"),
    ]


def feature_frame(cohort: pd.DataFrame, groups: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """All candidate features; race dummies use the reference group as baseline."""
    frame = cohort[["age", "female", "bmi", "family_history", "insured", "routine_care"]].astype(float).copy()
    race_columns = []
    for group in groups:
        if group == REFERENCE_RACE:
            continue
        column = f"race_{group}"
        frame[column] = (cohort["race_label"] == group).astype(float)
        race_columns.append(column)
    return frame, race_columns


def make_estimator(spec: ModelSpec, seed: int) -> Pipeline:
    if spec.algorithm == "logistic":
        return Pipeline(
            [
                ("impute", SimpleImputer(strategy="median", add_indicator=True)),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(C=1.0, max_iter=2000)),
            ]
        )
    if spec.algorithm == "boosting":
        return Pipeline(
            [
                ("model", HistGradientBoostingClassifier(
                    max_depth=3, learning_rate=0.05, max_iter=120, l2_regularization=1.0,
                    random_state=seed)),
            ]
        )
    raise ValueError(f"Unknown algorithm {spec.algorithm}")


def fit_predict(
    spec: ModelSpec, x_train: pd.DataFrame, y_train: np.ndarray, w_train: np.ndarray,
    x_test: pd.DataFrame, seed: int,
) -> np.ndarray:
    """Weighted fit; weights are rescaled to mean 1 so the L2 penalty keeps a stable meaning."""
    estimator = make_estimator(spec, seed)
    scaled = w_train / w_train.mean()
    estimator.fit(x_train[list(spec.columns)], y_train, model__sample_weight=scaled)
    return np.asarray(estimator.predict_proba(x_test[list(spec.columns)])[:, 1])


@dataclass(frozen=True)
class CvResult:
    probability: np.ndarray  # (repeats, n) out-of-fold probability
    prediction: np.ndarray  # (repeats, n) thresholded class
    thresholds: np.ndarray  # (repeats, folds) nested Youden thresholds


def cross_validate(
    spec: ModelSpec,
    x: pd.DataFrame,
    y: np.ndarray,
    w: np.ndarray,
    clusters: np.ndarray,
    stratify: np.ndarray,
    folds: int,
    repeats: int,
    inner_folds: int,
    seed: int,
) -> CvResult:
    """Repeated stratified grouped K-fold with the threshold chosen inside each training fold.

    Folds are grouped by design cluster (stratum x PSU) so respondents sharing a PSU never sit on
    both sides of a split. The Youden threshold is picked from inner out-of-fold predictions on the
    training clusters only, then applied unchanged to the held-out fold.
    """
    n = len(y)
    prob = np.full((repeats, n), np.nan)
    pred = np.zeros((repeats, n))
    thresholds = np.full((repeats, folds), np.nan)
    for r in range(repeats):
        outer = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed + r)
        for k, (train, test) in enumerate(outer.split(x, stratify, clusters)):
            inner = StratifiedGroupKFold(n_splits=inner_folds, shuffle=True, random_state=seed + 100 + r)
            oof = np.full(len(train), np.nan)
            x_train = x.iloc[train]
            for inner_train, inner_test in inner.split(x_train, stratify[train], clusters[train]):
                oof[inner_test] = fit_predict(
                    spec, x_train.iloc[inner_train], y[train][inner_train], w[train][inner_train],
                    x_train.iloc[inner_test], seed)
            threshold = youden_threshold(y[train], oof, w[train])
            p_test = fit_predict(spec, x_train, y[train], w[train], x.iloc[test], seed)
            prob[r, test] = p_test
            pred[r, test] = p_test >= threshold
            thresholds[r, k] = threshold
    if np.isnan(prob).any():
        raise RuntimeError("Cross-validation left respondents without an out-of-fold prediction")
    return CvResult(prob, pred, thresholds)


def spec_table(specs: list[ModelSpec]) -> list[dict[str, Any]]:
    return [
        {"model": s.name, "algorithm": s.algorithm, "role": s.role,
         "features": ", ".join(s.columns), "description": s.description}
        for s in specs
    ]
