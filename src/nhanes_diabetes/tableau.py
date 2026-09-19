"""Write the Tableau data package: three aggregated extracts, a field dictionary and expected KPIs.

This module prepares data only. It does not build, and no file in this repository claims, a Tableau
workbook. See tableau/README.md for the manual checkpoint.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from nhanes_diabetes.config import Config
from nhanes_diabetes.report import ALL, RACE, load_tables
from nhanes_diabetes.workbook import ALPHA

TABLEAU_DIR = Path("tableau")

DESCRIPTIONS: dict[str, str] = {
    "group": "Race and ethnicity group, or All groups.",
    "is_all_groups": "True for the All groups row. Use it to separate the total from the group rows.",
    "hba1c_positive_respondents": "Unweighted respondents meeting the HbA1c criterion (the denominator group).",
    "undiagnosed_respondents": "Unweighted respondents meeting the criterion who were never told they have diabetes.",
    "weighted_denominator": "Survey-weighted people meeting the HbA1c criterion.",
    "weighted_undiagnosed": "Survey-weighted people meeting the criterion who were never told they have diabetes.",
    "undiagnosed_share": "Weighted undiagnosed share of people meeting the HbA1c criterion (0 to 1).",
    "ci_low": "Lower bound of the 95% logit interval, or of the metric interval in model_tradeoffs.csv.",
    "ci_high": "Upper bound of the 95% logit interval, or of the metric interval in model_tradeoffs.csv.",
    "effective_n_kish": "Kish effective sample size of the group.",
    "small_sample_warning": "SMALL SAMPLE when the group has fewer than 30 respondents or an effective n under 30, else OK.",
    "difference_vs_reference": "Undiagnosed share minus the reference group's share (0 to 1 scale). Empty for the reference group and All groups.",
    "diff_ci_low": "Lower bound of the 95% interval for the difference.",
    "diff_ci_high": "Upper bound of the 95% interval for the difference.",
    "ratio": "Undiagnosed share divided by the reference group's share.",
    "ratio_ci_low": "Lower bound of the 95% interval for the ratio.",
    "ratio_ci_high": "Upper bound of the 95% interval for the ratio.",
    "p_value": "Unadjusted p-value for the difference.",
    "p_value_holm": "Holm-adjusted p-value across the comparisons with the reference group.",
    "analysis_type": "confirmatory for the one pre-specified comparison, exploratory for the rest.",
    "review_label": "Reference group, Pre-specified comparison, or Exploratory with the Holm result at the display threshold.",
    "model": "Model identifier from model_specification.csv.",
    "model_role": "primary, sensitivity or comparison.",
    "model_description": "Plain-English model description.",
    "label": "Training label (diagnosed or hba1c_pos), or diagnosed minus hba1c_pos for paired comparisons.",
    "metric": "auc, auc_difference, sensitivity, specificity, false_positive_rate, ppv, npv or specificity_cost.",
    "estimate": "Value of the metric. Rates and shares are on a 0 to 1 scale.",
    "unit": "proportion, auc or percentage points (0 to 1 scale).",
    "step": "Cohort step number.",
    "criterion": "Inclusion or exclusion criterion applied at the step.",
    "remaining": "Respondents remaining after the step.",
    "removed": "Respondents removed by the step.",
    "share_of_participants_remaining": "Remaining divided by the first step, on a 0 to 1 scale.",
    "kpi": "Name of the value a Tableau worksheet must reproduce.",
    "value": "Expected value from the pipeline.",
    "source": "Pipeline table the value comes from.",
}


def _flag(value: object) -> str:
    return "SMALL SAMPLE" if bool(value) else "OK"


def care_gap_summary(t: dict[str, pd.DataFrame], config: Config) -> pd.DataFrame:
    est = t["undiagnosis_estimates"].set_index("group")
    summary = t["group_summary"].set_index("group_name")
    con = t["undiagnosis_contrasts"].set_index("group")
    rows = []
    for g in config.groups + [ALL]:
        e, s = est.loc[g], summary.loc[g]
        row: dict[str, object] = {
            "group": g, "is_all_groups": g == ALL,
            "hba1c_positive_respondents": int(e["respondents"]),
            "undiagnosed_respondents": int(s["undiagnosed_among_positive"]),
            "weighted_denominator": float(e["weighted_denominator"]),
            "weighted_undiagnosed": float(s["weighted_undiagnosed"]),
            "undiagnosed_share": float(e["estimate"]), "ci_low": float(e["ci_low_logit"]),
            "ci_high": float(e["ci_high_logit"]), "effective_n_kish": float(e["effective_n_kish"]),
            "small_sample_warning": _flag(e["small_n_warning"]),
            "difference_vs_reference": None, "diff_ci_low": None, "diff_ci_high": None, "ratio": None,
            "ratio_ci_low": None, "ratio_ci_high": None, "p_value": None, "p_value_holm": None,
            "analysis_type": None, "review_label": "Reference group" if g == config.analysis("reference_group") else None,
        }
        if g in con.index:
            c = con.loc[g]
            row.update({"difference_vs_reference": float(c["difference"]), "diff_ci_low": float(c["ci_low"]),
                        "diff_ci_high": float(c["ci_high"]), "ratio": float(c["ratio"]),
                        "ratio_ci_low": float(c["ratio_ci_low"]), "ratio_ci_high": float(c["ratio_ci_high"]),
                        "p_value": float(c["p_value"]), "p_value_holm": float(c["p_value_holm"]),
                        "analysis_type": str(c["analysis_type"])})
            if c["analysis_type"] == "confirmatory":
                row["review_label"] = "Pre-specified comparison"
            else:
                verdict = "below" if c["p_value_holm"] < ALPHA else "not below"
                row["review_label"] = f"Exploratory: {verdict} {ALPHA} after Holm adjustment"
        rows.append(row)
    return pd.DataFrame(rows)


def model_tradeoffs(t: dict[str, pd.DataFrame], config: Config) -> pd.DataFrame:
    spec = t["model_specification"].set_index("model")
    sub, auc, diff, cost = t["subgroup_metrics"], t["auc"], t["auc_difference"].set_index("model"), t["specificity_cost"]
    rows: list[dict[str, object]] = []

    def add(model: str, group: str, label: str, metric: str, unit: str, est: float, lo: float | None,
            hi: float | None, small: object) -> None:
        rows.append({"model": model, "model_role": spec.loc[model, "role"], "model_description": spec.loc[model, "description"],
                     "group": group, "label": label, "metric": metric, "estimate": float(est),
                     "ci_low": None if lo is None else float(lo), "ci_high": None if hi is None else float(hi),
                     "unit": unit, "small_sample_warning": _flag(small)})

    for r in sub.itertuples():
        for metric in ("sensitivity", "specificity", "ppv", "npv"):
            lo, hi = getattr(r, f"{metric}_ci_low"), getattr(r, f"{metric}_ci_high")
            add(r.model, r.group, r.label, metric, "proportion", getattr(r, metric),
                None if pd.isna(lo) else lo, None if pd.isna(hi) else hi, r.small_n_warning)
        add(r.model, r.group, r.label, "false_positive_rate", "proportion", 1 - r.specificity,
            None if pd.isna(r.specificity_ci_high) else 1 - r.specificity_ci_high,
            None if pd.isna(r.specificity_ci_low) else 1 - r.specificity_ci_low, r.small_n_warning)
    for r in auc[auc["evaluated_against"] == "hba1c_criterion"].itertuples():
        add(r.model, ALL, r.label, "auc", "auc", r.auc, r.ci_low, r.ci_high, False)
    for model in spec.index:
        d = diff.loc[model]
        add(model, ALL, "diagnosed minus hba1c_pos", "auc_difference", "auc", d["difference"], d["ci_low"], d["ci_high"], False)
    for r in cost.itertuples():
        add(r.model, r.group, "diagnosed minus hba1c_pos", "specificity_cost", "percentage points (0 to 1 scale)",
            r.cost, r.ci_low, r.ci_high, False)
    frame = pd.DataFrame(rows)
    order = {m: i for i, m in enumerate(spec.index)}
    frame["_m"] = frame["model"].map(order)
    return frame.sort_values(["_m", "metric", "label", "group"], kind="stable").drop(columns="_m").reset_index(drop=True)


def cohort_flow(t: dict[str, pd.DataFrame], config: Config) -> pd.DataFrame:
    att = t["cohort_attrition"].rename(columns={"description": "criterion", "n": "remaining"})
    first = float(att["remaining"].iloc[0])
    att = att.assign(share_of_participants_remaining=att["remaining"] / first)
    return att[["step", "criterion", "remaining", "removed", "share_of_participants_remaining"]]


def expected_kpis(t: dict[str, pd.DataFrame], config: Config) -> pd.DataFrame:
    est = t["undiagnosis_estimates"].set_index("group")
    con = t["undiagnosis_contrasts"].set_index("group")
    cost = t["specificity_cost"]
    comparison = str(config.analysis("comparison_group"))
    race_cost = cost[(cost["model"] == RACE) & (cost["group"] == comparison)].iloc[0]
    rows = [
        ("undiagnosed_share_all_groups", est.loc[ALL, "estimate"], "undiagnosis_estimates.csv"),
        (f"undiagnosed_share_{comparison}", est.loc[comparison, "estimate"], "undiagnosis_estimates.csv"),
        ("difference_vs_reference_prespecified", con.loc[comparison, "difference"], "undiagnosis_contrasts.csv"),
        ("weighted_people_undiagnosed", t["group_summary"].set_index("group_name").loc[ALL, "weighted_undiagnosed"], "group_summary.csv"),
        ("specificity_cost_race_included_comparison_group", race_cost["cost"], "specificity_cost.csv"),
        ("analysis_cohort_respondents", t["cohort_attrition"]["n"].iloc[-1], "cohort_attrition.csv"),
    ]
    return pd.DataFrame(rows, columns=["kpi", "value", "source"])


def field_dictionary(frames: dict[str, pd.DataFrame]) -> str:
    lines = ["# Field dictionary", "",
             "Generated by `nhanes-diabetes tableau`. One section per extract in `tableau/data/`. "
             "Public NHANES 2017-2018 survey aggregates; no respondent-level rows.", ""]
    for name, frame in frames.items():
        lines += [f"## {name}.csv", "", f"{len(frame):,} rows.", "", "| Field | Type | Meaning |", "|---|---|---|"]
        for column, dtype in frame.dtypes.items():
            kind = "number" if pd.api.types.is_numeric_dtype(dtype) and not pd.api.types.is_bool_dtype(dtype) \
                else "boolean" if pd.api.types.is_bool_dtype(dtype) else "text"
            lines.append(f"| `{column}` | {kind} | {DESCRIPTIONS.get(str(column), '')} |")
        lines.append("")
    return "\n".join(lines)


def build_frames(config: Config) -> dict[str, pd.DataFrame]:
    t = load_tables(config)
    return {"care_gap_summary": care_gap_summary(t, config), "model_tradeoffs": model_tradeoffs(t, config),
            "cohort_flow": cohort_flow(t, config)}


def render_tableau(config: Config) -> dict[str, str]:
    """Relative path to the exact text of each generated file."""
    t = load_tables(config)
    frames = build_frames(config)
    out = {f"data/{name}.csv": frame.to_csv(index=False, float_format="%.10g") for name, frame in frames.items()}
    out["expected_kpis.csv"] = expected_kpis(t, config).to_csv(index=False, float_format="%.10g")
    out["field_dictionary.md"] = field_dictionary(frames | {"expected_kpis": expected_kpis(t, config)})
    return out


def write_tableau(config: Config) -> Path:
    root = config.root / TABLEAU_DIR
    for rel, text in render_tableau(config).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def check_tableau(config: Config) -> list[str]:
    root = config.root / TABLEAU_DIR
    problems = []
    for rel, text in render_tableau(config).items():
        path = root / rel
        if not path.exists():
            problems.append(f"tableau/{rel} is missing")
        elif path.read_text(encoding="utf-8") != text:
            problems.append(f"tableau/{rel} does not match outputs/tables")
    return problems
