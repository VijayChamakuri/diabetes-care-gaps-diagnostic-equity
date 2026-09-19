"""Evaluate diagnosed-label and HbA1c-label models against the HbA1c criterion, with uncertainty.

Every model is scored out-of-fold (repeated stratified grouped cross-validation, nested threshold
selection). Uncertainty comes from the Rao-Wu rescaled PSU bootstrap applied to those fixed
out-of-fold predictions, so it reflects survey-design sampling variability but not refitting
variability. That limit is stated in docs/methods.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from nhanes_diabetes.config import Config
from nhanes_diabetes.metrics import (
    calibration_bins,
    confusion_sums,
    rates,
    weighted_auc,
    weighted_brier,
)
from nhanes_diabetes.models import (
    CvResult,
    cross_validate,
    feature_frame,
    model_specs,
    spec_table,
)
from nhanes_diabetes.survey import Design, kish_effective_n, rao_wu_multipliers, row_multipliers

LABEL_ORDER = ("diagnosed", "hba1c_pos")
METRICS = ("sensitivity", "specificity", "ppv", "npv")
FEATURE_NOTES = {
    "age": ("RIDAGEYR", "Age in years at screening", "Known before any diagnosis; top-coded at 80"),
    "female": ("RIAGENDR", "Female sex", "Known before any diagnosis"),
    "bmi": ("BMXBMI", "Body mass index from the exam",
            "Measured at the same exam as HbA1c but not part of the outcome definition"),
    "family_history": ("MCQ300C", "Close relative with diabetes (adults 20 and older)",
                       "Self-reported; blank for adolescents, so imputed with a missing indicator"),
    "insured": ("HIQ011", "Covered by health insurance", "Access-to-care proxy, known before diagnosis"),
    "routine_care": ("HUQ030", "Has a place for routine care", "Access-to-care proxy, known before diagnosis"),
}


def _percentile(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    if finite.size < 20:
        return float("nan"), float("nan")
    return float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))


@dataclass
class Evaluation:
    tables: dict[str, pd.DataFrame]
    thresholds_mean: dict[str, float]


def _boot_rates(
    y: np.ndarray, cv: CvResult, weights: np.ndarray, mask: np.ndarray
) -> dict[str, np.ndarray]:
    """Metric arrays of shape (B + 1,) averaged over CV repeats; index 0 is the point estimate."""
    per_repeat = []
    for r in range(cv.prediction.shape[0]):
        tp, fn, tn, fp = confusion_sums(y, cv.prediction[r], weights, mask)
        per_repeat.append(rates(tp, fn, tn, fp))
    return {m: np.nanmean(np.vstack([p[m] for p in per_repeat]), axis=0) for m in METRICS}


def evaluate_models(cohort: pd.DataFrame, design: Design, config: Config) -> Evaluation:
    seed = int(config.analysis("seed"))
    folds, repeats = config.validation("folds"), config.validation("repeats")
    inner = config.validation("inner_folds")
    replicates = config.validation("bootstrap_replicates")
    groups = config.groups
    min_pos, min_neff = config.analysis("min_positives"), config.analysis("min_effective_n")

    x, race_columns = feature_frame(cohort, groups)
    specs = model_specs(race_columns)
    w = cohort["weight"].to_numpy(dtype=float)
    truth = cohort["hba1c_pos"].to_numpy(dtype=float)
    labels = {"diagnosed": cohort["diagnosed"].to_numpy(dtype=float), "hba1c_pos": truth}
    rng = np.random.default_rng(seed)
    multipliers = row_multipliers(design, rao_wu_multipliers(design, rng, replicates))
    weights = np.vstack([w[None, :], w[None, :] * multipliers])  # row 0 is the point estimate

    masks = {g: (cohort["race_label"] == g).to_numpy() for g in groups}
    masks["All groups"] = np.ones(len(cohort), dtype=bool)

    fits: dict[tuple[str, str], CvResult] = {}
    for spec in specs:
        for label in LABEL_ORDER:
            fits[(spec.name, label)] = cross_validate(
                spec, x, labels[label], w, design.cluster, truth, folds, repeats, inner, seed)

    subgroup_rows, arrays = [], {}
    for (spec_name, label), cv in fits.items():
        for group, mask in masks.items():
            metric_arrays = _boot_rates(truth, cv, weights, mask)
            arrays[(spec_name, label, group)] = metric_arrays
            pos, neg = mask & (truth == 1), mask & (truth == 0)
            row = {"model": spec_name, "label": label, "group": group,
                   "respondents": int(mask.sum()), "positives": int(pos.sum()), "negatives": int(neg.sum()),
                   "effective_n_positives": kish_effective_n(w[pos]),
                   "effective_n_negatives": kish_effective_n(w[neg]),
                   "small_n_warning": bool(pos.sum() < min_pos or kish_effective_n(w[pos]) < min_neff)}
            for m in METRICS:
                lo, hi = _percentile(metric_arrays[m][1:])
                row.update({m: float(metric_arrays[m][0]), f"{m}_ci_low": lo, f"{m}_ci_high": hi})
            subgroup_rows.append(row)
    subgroup = pd.DataFrame(subgroup_rows)

    cost_rows, gap_rows = [], []
    ref = config.analysis("reference_group")
    for spec in specs:
        for group in groups + ["All groups"]:
            a = arrays[(spec.name, "diagnosed", group)]["specificity"]
            b = arrays[(spec.name, "hba1c_pos", group)]["specificity"]
            cost = a - b
            lo, hi = _percentile(cost[1:])
            cost_rows.append({"model": spec.name, "group": group,
                              "specificity_diagnosed": float(a[0]), "specificity_hba1c": float(b[0]),
                              "cost": float(cost[0]), "ci_low": lo, "ci_high": hi})
        for group in groups:
            if group == ref:
                continue
            gaps = {}
            for label in LABEL_ORDER:
                s_ref = arrays[(spec.name, label, ref)]["sensitivity"]
                s_grp = arrays[(spec.name, label, group)]["sensitivity"]
                gaps[label] = s_ref - s_grp  # positive means the group is missed more often
            change = gaps["diagnosed"] - gaps["hba1c_pos"]
            row = {"model": spec.name, "group": group}
            for label, arr in (("diagnosed", gaps["diagnosed"]), ("hba1c_pos", gaps["hba1c_pos"]), ("change", change)):
                lo, hi = _percentile(arr[1:])
                row.update({f"gap_{label}": float(arr[0]), f"gap_{label}_ci_low": lo, f"gap_{label}_ci_high": hi})
            gap_rows.append(row)

    auc_rows, diff_rows, brier_rows, cal_rows = [], [], [], []
    auc_boot: dict[tuple[str, str, str], np.ndarray] = {}
    for (spec_name, label), cv in fits.items():
        p = cv.probability.mean(axis=0)
        y_own = labels[label]
        for target, y_target in (("hba1c_criterion", truth), ("own_label", y_own)):
            if target == "own_label" and label == "hba1c_pos":
                continue
            series = np.array([weighted_auc(y_target, p, weights[b]) for b in range(weights.shape[0])])
            auc_boot[(spec_name, label, target)] = series
            lo, hi = _percentile(series[1:])
            auc_rows.append({"model": spec_name, "label": label, "evaluated_against": target,
                             "auc": float(series[0]), "ci_low": lo, "ci_high": hi})
        for group, mask in masks.items():
            brier_rows.append({"model": spec_name, "label": label, "group": group,
                               "respondents": int(mask.sum()),
                               "brier_own_label": weighted_brier(y_own[mask], p[mask], w[mask])})
        for group, mask in masks.items():
            bins = 10 if group == "All groups" else 5
            if mask.sum() < 100:
                continue
            for bin_row in calibration_bins(y_own[mask], p[mask], w[mask], bins):
                cal_rows.append({"model": spec_name, "label": label, "group": group, **bin_row})
    for spec in specs:
        d = auc_boot[(spec.name, "diagnosed", "hba1c_criterion")] - auc_boot[(spec.name, "hba1c_pos", "hba1c_criterion")]
        boot = d[1:]
        p_value = 2 * min(float((boot <= 0).mean()), float((boot >= 0).mean()))
        lo, hi = _percentile(boot)
        diff_rows.append({"model": spec.name, "auc_diagnosed_label": float(auc_boot[(spec.name, "diagnosed", "hba1c_criterion")][0]),
                          "auc_hba1c_label": float(auc_boot[(spec.name, "hba1c_pos", "hba1c_criterion")][0]),
                          "difference": float(d[0]), "ci_low": lo, "ci_high": hi,
                          "p_value_bootstrap": max(p_value, 2.0 / (len(boot) + 1)),
                          "bootstrap_replicates": len(boot)})

    threshold_rows = []
    means = {}
    for (spec_name, label), cv in fits.items():
        t = cv.thresholds.ravel()
        threshold_rows.append({"model": spec_name, "label": label, "mean": float(t.mean()),
                               "sd": float(t.std()), "min": float(t.min()), "max": float(t.max())})
        means[f"{spec_name}:{label}"] = float(t.mean())

    features = []
    for spec in specs:
        for column in spec.columns:
            code, name, note = FEATURE_NOTES.get(column, ("RIDRETH3", f"Race and ethnicity: {column.removeprefix('race_')}",
                                                          "Sensitivity analysis only, never in the primary model"))
            features.append({"model": spec.name, "role": spec.role, "feature": column, "nhanes_variable": code,
                             "description": name, "availability_and_rationale": note})
    tables = {
        "model_specification": pd.DataFrame(spec_table(specs)),
        "feature_specification": pd.DataFrame(features),
        "subgroup_metrics": subgroup,
        "specificity_cost": pd.DataFrame(cost_rows),
        "sensitivity_gap": pd.DataFrame(gap_rows),
        "auc": pd.DataFrame(auc_rows),
        "auc_difference": pd.DataFrame(diff_rows),
        "brier_by_group": pd.DataFrame(brier_rows),
        "calibration": pd.DataFrame(cal_rows),
        "thresholds": pd.DataFrame(threshold_rows),
    }
    return Evaluation(tables, means)

