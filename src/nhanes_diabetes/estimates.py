"""Survey-weighted descriptive and inferential tables for the undiagnosed-diabetes gap."""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from nhanes_diabetes.cohort import Variant, build_cohort
from nhanes_diabetes.config import Config
from nhanes_diabetes.survey import (
    Design,
    Estimate,
    contrast,
    estimate_mean,
    holm_adjust,
    standardized_proportion,
)

ALL = "All groups"


def _domains(cohort: pd.DataFrame, groups: list[str]) -> dict[str, np.ndarray]:
    out = {g: (cohort["race_label"] == g).to_numpy() for g in groups}
    out[ALL] = np.ones(len(cohort), dtype=bool)
    return out


def _estimate_row(name: str, e: Estimate, min_positives: int, min_neff: int) -> dict[str, object]:
    return {
        "group": name,
        "respondents": e.n,
        "weighted_denominator": e.weighted_total,
        "effective_n_kish": e.n_eff_kish,
        "effective_n_design": e.n_eff_design,
        "estimate": e.estimate,
        "se": e.se,
        "ci_low_logit": e.ci_logit[0],
        "ci_high_logit": e.ci_logit[1],
        "ci_low_wald": e.ci_wald[0],
        "ci_high_wald": e.ci_wald[1],
        "df": e.df,
        "small_n_warning": bool(e.n < min_positives or e.n_eff_kish < min_neff),
    }


def undiagnosis_table(cohort: pd.DataFrame, design: Design, config: Config) -> pd.DataFrame:
    """Share of respondents meeting the HbA1c criterion who were never told they have diabetes."""
    pos = (cohort["hba1c_pos"] == 1).to_numpy()
    undiagnosed = 1.0 - cohort["diagnosed"].to_numpy(dtype=float)
    rows = []
    for name, dom in _domains(cohort, config.groups).items():
        e = estimate_mean(design, undiagnosed, pos & dom)
        rows.append(_estimate_row(name, e, config.analysis("min_positives"), config.analysis("min_effective_n")))
    return pd.DataFrame(rows)


def contrast_table(cohort: pd.DataFrame, design: Design, config: Config) -> pd.DataFrame:
    """Each group against the reference. Only the pre-specified comparison is confirmatory."""
    ref = config.analysis("reference_group")
    primary = config.analysis("comparison_group")
    pos = (cohort["hba1c_pos"] == 1).to_numpy()
    undiagnosed = 1.0 - cohort["diagnosed"].to_numpy(dtype=float)
    doms = _domains(cohort, config.groups)
    names = [g for g in config.groups if g != ref]
    results = [contrast(design, undiagnosed, pos & doms[g], pos & doms[ref]) for g in names]
    adjusted = holm_adjust([c.p_value for c in results])
    rows = []
    for g, c, p_holm in zip(names, results, adjusted, strict=True):
        rows.append(
            {
                "group": g,
                "reference": ref,
                "difference": c.difference,
                "se": c.se,
                "ci_low": c.ci[0],
                "ci_high": c.ci[1],
                "df": c.df,
                "t": c.t,
                "p_value": c.p_value,
                "p_value_holm": p_holm,
                "ratio": c.ratio,
                "ratio_ci_low": c.ratio_ci[0],
                "ratio_ci_high": c.ratio_ci[1],
                "analysis_type": "confirmatory" if g == primary else "exploratory",
            }
        )
    return pd.DataFrame(rows)


def prevalence_table(cohort: pd.DataFrame, design: Design, config: Config) -> pd.DataFrame:
    """Weighted prevalence of the HbA1c criterion, doctor-told diagnosis, and the undiagnosed share."""
    hba = cohort["hba1c_pos"].to_numpy(dtype=float)
    diagnosed = cohort["diagnosed"].to_numpy(dtype=float)
    undiagnosed_all = hba * (1 - diagnosed)
    rows = []
    for name, dom in _domains(cohort, config.groups).items():
        for measure, y in (
            ("hba1c_criterion", hba),
            ("told_by_doctor", diagnosed),
            ("hba1c_criterion_and_not_told", undiagnosed_all),
        ):
            e = estimate_mean(design, y, dom)
            rows.append(
                {"group": name, "measure": measure, "respondents": e.n, "estimate": e.estimate,
                 "se": e.se, "ci_low_logit": e.ci_logit[0], "ci_high_logit": e.ci_logit[1],
                 "weighted_denominator": e.weighted_total}
            )
    return pd.DataFrame(rows)


def baseline_characteristics(cohort: pd.DataFrame, design: Design, config: Config) -> pd.DataFrame:
    """Survey-weighted descriptive table for the cohort and the HbA1c-positive subpopulations."""
    pos = (cohort["hba1c_pos"] == 1).to_numpy()
    diag = (cohort["diagnosed"] == 1).to_numpy()
    domains = {
        "Analysis cohort": np.ones(len(cohort), dtype=bool),
        "HbA1c criterion met": pos,
        "Met criterion, told by doctor": pos & diag,
        "Met criterion, never told": pos & ~diag,
    }
    measures = [("age", "Age, years", False), ("female", "Female", True), ("bmi", "BMI, kg/m2", False),
                ("insured", "Has health insurance", True), ("routine_care", "Has a routine place for care", True),
                ("family_history", "Close relative with diabetes", True)]
    rows = []
    for domain_name, dom in domains.items():
        for column, label, is_share in measures:
            values = cohort[column].to_numpy(dtype=float)
            usable = dom & ~np.isnan(values)
            if not usable.any():
                continue
            e = estimate_mean(design, np.nan_to_num(values), usable, bounded=is_share)
            rows.append({"population": domain_name, "characteristic": label, "respondents": e.n,
                         "estimate": e.estimate, "se": e.se, "kind": "share" if is_share else "mean"})
        for group in config.groups:
            e = estimate_mean(design, (cohort["race_label"] == group).to_numpy(dtype=float), dom)
            rows.append({"population": domain_name, "characteristic": f"Race and ethnicity: {group}",
                         "respondents": e.n, "estimate": e.estimate, "se": e.se, "kind": "share"})
    return pd.DataFrame(rows)


def missingness_table(cohort: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Unweighted missingness of every model input by group, in the full cohort."""
    variables = ["bmi", "family_history", "insured", "routine_care"]
    rows = []
    for name, dom in _domains(cohort, config.groups).items():
        sub = cohort[dom]
        for v in variables:
            rows.append({"group": name, "variable": v, "respondents": len(sub),
                         "missing": int(sub[v].isna().sum()), "missing_share": float(sub[v].isna().mean())})
    return pd.DataFrame(rows)


def age_standardized_table(cohort: pd.DataFrame, design: Design, config: Config) -> pd.DataFrame:
    """Direct age standardization to the age mix of everyone meeting the HbA1c criterion."""
    pos = (cohort["hba1c_pos"] == 1).to_numpy()
    undiagnosed = 1.0 - cohort["diagnosed"].to_numpy(dtype=float)
    age = cohort["age"].to_numpy(dtype=float)
    bands = [((age >= lo) & (age <= hi)).astype(float) for lo, hi in config.analysis("age_bands")]
    totals = np.array([(design.weight * pos * b).sum() for b in bands])
    standard = totals / totals.sum()
    labels = [f"{lo}-{hi}" for lo, hi in config.analysis("age_bands")]
    ref = config.analysis("reference_group")
    rows = []
    doms = _domains(cohort, config.groups)
    mean_age = {}
    for name, dom in doms.items():
        d = pos & dom
        e = estimate_mean(design, age, d, bounded=False)
        mean_age[name] = e.estimate
        std = standardized_proportion(design, undiagnosed, d.astype(float), bands, standard)
        crude = estimate_mean(design, undiagnosed, d)
        rows.append({"group": name, "respondents": std.n, "mean_age": e.estimate,
                     "crude_estimate": crude.estimate, "age_standardized_estimate": std.estimate,
                     "se": std.se, "ci_low": std.ci_wald[0], "ci_high": std.ci_wald[1],
                     "standard_bands": ", ".join(labels),
                     "standard_shares": ", ".join(f"{s:.3f}" for s in standard)})
    out = pd.DataFrame(rows)
    out["age_difference_vs_reference"] = out["group"].map(lambda g: mean_age[g] - mean_age[ref])
    out["age_mix_differs"] = out["age_difference_vs_reference"].abs() > 5
    return out


def _variant_row(label: str, cohort: pd.DataFrame, design: Design, config: Config,
                 extra: np.ndarray | None = None) -> dict[str, object]:
    ref, primary = config.analysis("reference_group"), config.analysis("comparison_group")
    pos = (cohort["hba1c_pos"] == 1).to_numpy()
    undiagnosed = 1.0 - cohort["diagnosed"].to_numpy(dtype=float)
    keep = np.ones(len(cohort), dtype=bool) if extra is None else extra
    a = pos & keep & (cohort["race_label"] == primary).to_numpy()
    b = pos & keep & (cohort["race_label"] == ref).to_numpy()
    ea, eb = estimate_mean(design, undiagnosed, a), estimate_mean(design, undiagnosed, b)
    c = contrast(design, undiagnosed, a, b)
    return {"analysis": label, "cohort_respondents": int(keep.sum()),
            "hba1c_positive": int((pos & keep).sum()),
            "comparison_estimate": ea.estimate, "reference_estimate": eb.estimate,
            "difference": c.difference, "ci_low": c.ci[0], "ci_high": c.ci[1],
            "ratio": c.ratio, "p_value": c.p_value}


def robustness_table(con: duckdb.DuckDBPyConnection, config: Config, main: pd.DataFrame) -> pd.DataFrame:
    """Pre-specified alternatives to the main cohort definition, in one table."""
    rows = [_variant_row("Main analysis", main, Design.from_frame(main, lonely=config.lonely_psu), config)]
    complete = main[["bmi", "family_history", "insured", "routine_care"]].notna().all(axis=1).to_numpy()
    rows.append(_variant_row("Complete cases for extended covariates", main,
                             Design.from_frame(main, lonely=config.lonely_psu), config, complete))
    variants = [Variant("borderline_positive", "positive"), Variant("borderline_negative", "negative"),
                Variant("adults_only", "exclude", 18)]
    labels = {"borderline_positive": "Borderline answers counted as diagnosed",
              "borderline_negative": "Borderline answers counted as not diagnosed",
              "adults_only": "Adults 18 and older only"}
    try:
        for v in variants:
            cohort = build_cohort(con, config, v).data
            rows.append(_variant_row(labels[v.name], cohort, Design.from_frame(cohort, lonely=config.lonely_psu), config))
    finally:
        build_cohort(con, config, Variant())  # leave the database in the main-analysis state
    return pd.DataFrame(rows)
