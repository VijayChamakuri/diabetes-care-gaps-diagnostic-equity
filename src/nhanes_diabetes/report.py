"""Generate the README's numeric blocks from outputs/tables, and check they have not drifted.

Every number in the README lives inside a ``<!-- BEGIN generated:NAME -->`` block. Prose outside the
blocks carries no statistics, and ``tests/test_readme.py`` enforces that.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pandas as pd

from nhanes_diabetes.config import Config

PRIMARY, RACE = "demographic_logistic", "demographic_race_logistic"
ALL = "All groups"
MARK = re.compile(r"(<!-- BEGIN generated:(?P<name>[a-z_]+) -->\n)(?P<body>.*?)(<!-- END generated:(?P=name) -->)", re.S)


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def span(lo: float, hi: float, digits: int = 1) -> str:
    return f"{lo * 100:.{digits}f}% to {hi * 100:.{digits}f}%"


def pp(x: float, digits: int = 1) -> str:
    return f"{x * 100:+.{digits}f} pp"


def pp_span(lo: float, hi: float) -> str:
    return f"{lo * 100:+.1f} to {hi * 100:+.1f} pp"


def signed(x: float, digits: int = 3) -> str:
    """Signed fixed-point that never prints negative zero."""
    text = f"{x:+.{digits}f}"
    return f"{0:.{digits}f}" if float(text) == 0 else text


def pval(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def millions(x: float) -> str:
    return f"{x / 1e6:.1f} million"


def md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def _row(df: pd.DataFrame, **conditions: object) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    for column, value in conditions.items():
        mask &= df[column] == value
    if mask.sum() != 1:
        raise KeyError(f"Expected one row for {conditions}, found {int(mask.sum())}")
    return df[mask].iloc[0]


def block_headline(t: dict[str, pd.DataFrame], config: Config) -> str:
    est, con = t["undiagnosis_estimates"], t["undiagnosis_contrasts"]
    overall = _row(est, group=ALL)
    black = _row(est, group=config.analysis("comparison_group"))
    white = _row(est, group=config.analysis("reference_group"))
    c = _row(con, group=config.analysis("comparison_group"))
    diff = t["auc_difference"].set_index("model")
    cost = t["specificity_cost"]
    primary_all = _row(cost, model=PRIMARY, group=ALL)
    race_black = _row(cost, model=RACE, group=config.analysis("comparison_group"))
    race_white = _row(cost, model=RACE, group=config.analysis("reference_group"))
    return "\n".join([
        f"1. **Undiagnosed diabetes gap.** Of {int(overall.respondents):,} respondents meeting the HbA1c criterion "
        f"({millions(overall.weighted_denominator)} people once weighted), {pct(overall.estimate)} "
        f"({span(overall.ci_low_logit, overall.ci_high_logit)}) were never told they have diabetes. "
        f"Non-Hispanic Black respondents: {pct(black.estimate)} ({span(black.ci_low_logit, black.ci_high_logit)}; "
        f"n = {int(black.respondents)}, effective n = {black.effective_n_kish:.0f}). "
        f"Non-Hispanic White respondents: {pct(white.estimate)} ({span(white.ci_low_logit, white.ci_high_logit)}; "
        f"n = {int(white.respondents)}, effective n = {white.effective_n_kish:.0f}). "
        f"Difference {pp(c.difference)} (95% CI {pp_span(c.ci_low, c.ci_high)}, {pval(c.p_value)}), "
        f"ratio {c.ratio:.2f} (95% CI {c.ratio_ci_low:.2f} to {c.ratio_ci_high:.2f}). This is the one pre-specified comparison.",
        f"2. **With race excluded, the training label barely changes the primary age-and-sex model.** "
        f"AUC against the HbA1c criterion is {diff.loc[PRIMARY, 'auc_diagnosed_label']:.3f} for the diagnosed label and "
        f"{diff.loc[PRIMARY, 'auc_hba1c_label']:.3f} for the HbA1c label (difference "
        f"{signed(diff.loc[PRIMARY, 'difference'])}, 95% CI {signed(diff.loc[PRIMARY, 'ci_low'])} to "
        f"{signed(diff.loc[PRIMARY, 'ci_high'])}, bootstrap {pval(diff.loc[PRIMARY, 'p_value_bootstrap'])}). "
        f"Overall specificity cost {pp(primary_all.cost)} (95% CI {pp_span(primary_all.ci_low, primary_all.ci_high)}).",
        f"3. **In this comparison the label matters when race is a model input.** With race included, the specificity cost is "
        f"{pp(race_black.cost)} for Non-Hispanic Black respondents (95% CI {pp_span(race_black.ci_low, race_black.ci_high)}) "
        f"and {pp(race_white.cost)} for Non-Hispanic White respondents "
        f"(95% CI {pp_span(race_white.ci_low, race_white.ci_high)}).",
    ])


def block_cohort_flow(t: dict[str, pd.DataFrame], config: Config) -> str:
    rows = [[str(int(r.step)), r.description, f"{int(r.n):,}", f"{int(r.removed):,}"] for r in t["cohort_attrition"].itertuples()]
    return md_table(["Step", "Criterion", "Remaining", "Removed"], rows)


def block_undiagnosis(t: dict[str, pd.DataFrame], config: Config) -> str:
    est = t["undiagnosis_estimates"].set_index("group")
    rows = []
    for g in config.groups + [ALL]:
        r = est.loc[g]
        flag = " (small sample)" if r.small_n_warning else ""
        rows.append([g + flag, f"{int(r.respondents):,}", millions(r.weighted_denominator), f"{r.effective_n_kish:.0f}",
                     pct(r.estimate), span(r.ci_low_logit, r.ci_high_logit)])
    return md_table(["Group", "Respondents", "Weighted denominator", "Effective n", "Never told", "95% CI"], rows)


def block_contrasts(t: dict[str, pd.DataFrame], config: Config) -> str:
    rows = []
    for r in t["undiagnosis_contrasts"].itertuples():
        rows.append([r.group, pp(r.difference), pp_span(r.ci_low, r.ci_high), f"{r.ratio:.2f}",
                     pval(r.p_value), pval(r.p_value_holm), r.analysis_type])
    header = ["Group vs. " + config.analysis("reference_group"), "Difference", "95% CI", "Ratio",
              "p", "Holm-adjusted p", "Analysis"]
    return md_table(header, rows)


def block_models(t: dict[str, pd.DataFrame], config: Config) -> str:
    spec = t["model_specification"].set_index("model")
    diff = t["auc_difference"].set_index("model")
    cost = t["specificity_cost"]
    rows = []
    for m in spec.index:
        d = diff.loc[m]
        c = _row(cost, model=m, group=ALL)
        rows.append([spec.loc[m, "description"], spec.loc[m, "role"], f"{d.auc_diagnosed_label:.3f}",
                     f"{d.auc_hba1c_label:.3f}",
                     f"{signed(d.difference)} ({signed(d.ci_low)} to {signed(d.ci_high)})",
                     f"{pp(c.cost)} ({pp_span(c.ci_low, c.ci_high)})"])
    return md_table(["Model", "Role", "AUC, diagnosed label", "AUC, HbA1c label", "AUC difference (95% CI)",
                     "Overall specificity cost (95% CI)"], rows)


def block_subgroups(t: dict[str, pd.DataFrame], config: Config) -> str:
    sub = t["subgroup_metrics"]
    sub = sub[sub["model"] == PRIMARY]
    rows = []
    for g in config.groups + [ALL]:
        a = _row(sub, label="diagnosed", group=g)
        b = _row(sub, label="hba1c_pos", group=g)
        flag = " (small sample)" if a.small_n_warning else ""
        rows.append([g + flag, f"{int(a.positives)} ({a.effective_n_positives:.0f})",
                     f"{pct(a.sensitivity)} ({span(a.sensitivity_ci_low, a.sensitivity_ci_high, 0)})",
                     f"{pct(b.sensitivity)} ({span(b.sensitivity_ci_low, b.sensitivity_ci_high, 0)})",
                     pct(a.specificity), pct(b.specificity)])
    return md_table(["Group", "HbA1c positives (effective n)", "Sensitivity, diagnosed label",
                     "Sensitivity, HbA1c label", "Specificity, diagnosed label", "Specificity, HbA1c label"], rows)


def block_robustness(t: dict[str, pd.DataFrame], config: Config) -> str:
    rows = [[r.analysis, f"{int(r.cohort_respondents):,}", f"{int(r.hba1c_positive):,}", pct(r.comparison_estimate),
             pct(r.reference_estimate), f"{pp(r.difference)} ({pp_span(r.ci_low, r.ci_high)})", f"{r.ratio:.2f}",
             pval(r.p_value)] for r in t["robustness"].itertuples()]
    return md_table(["Analysis", "Cohort", "HbA1c positive", "Black", "White", "Difference (95% CI)", "Ratio", "p"], rows)


def block_crosscheck(t: dict[str, pd.DataFrame], config: Config) -> str:
    x = t.get("r_python_crosscheck")
    if x is None or x.empty:
        return "R cross-check has not been run."
    passed = int((x["status"] == "pass").sum())
    worst = float(x["absolute_difference"].max())
    return (f"{passed} of {len(x)} Python estimates match R `survey` within {x['tolerance'].iloc[0]:.0e} "
            f"(largest absolute difference {worst:.1e}). Table: `outputs/tables/r_python_crosscheck.csv`.")


BLOCKS: dict[str, Callable[[dict[str, pd.DataFrame], Config], str]] = {
    "headline": block_headline,
    "cohort_flow": block_cohort_flow,
    "undiagnosis": block_undiagnosis,
    "contrasts": block_contrasts,
    "models": block_models,
    "subgroups": block_subgroups,
    "robustness": block_robustness,
    "crosscheck": block_crosscheck,
}


def load_tables(config: Config) -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_csv(p) for p in config.tables_dir.glob("*.csv")}


def render_blocks(config: Config) -> dict[str, str]:
    tables = load_tables(config)
    return {name: fn(tables, config).strip() for name, fn in BLOCKS.items()}


def readme_path(config: Config):
    return config.root / "README.md"


def write_readme(config: Config) -> None:
    rendered = render_blocks(config)
    text = readme_path(config).read_text(encoding="utf-8")
    missing = [name for name in rendered if f"<!-- BEGIN generated:{name} -->" not in text]
    if missing:
        raise KeyError(f"README is missing generated blocks: {missing}")

    def replace(match: re.Match[str]) -> str:
        name = match.group("name")
        body = rendered.get(name)
        if body is None:
            return match.group(0)
        return f"{match.group(1)}{body}\n{match.group(4)}"

    readme_path(config).write_text(MARK.sub(replace, text), encoding="utf-8")


def check_readme(config: Config) -> list[str]:
    """Return one message per generated block whose README text differs from the tables."""
    rendered = render_blocks(config)
    text = readme_path(config).read_text(encoding="utf-8")
    found = {m.group("name"): m.group("body").strip() for m in MARK.finditer(text)}
    problems = []
    for name, expected in rendered.items():
        if name not in found:
            problems.append(f"block '{name}' is missing from README.md")
        elif found[name] != expected:
            problems.append(f"block '{name}' does not match outputs/tables")
    return problems
