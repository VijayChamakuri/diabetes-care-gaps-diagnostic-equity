"""Generate reports/healthcare_quality_brief.md from outputs/tables.

Every number in the brief is read from a generated table. The fixed prose (the decision question, the
limits, the next analysis) is kept in the constants below, and ``tests/test_brief.py`` proves that it
contains no statistics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from nhanes_diabetes.config import Config
from nhanes_diabetes.report import (
    ALL,
    PRIMARY,
    RACE,
    _row,
    block_cohort_flow,
    block_headline,
    load_tables,
    md_table,
    millions,
    pct,
    pp,
    pp_span,
    span,
)

BRIEF = Path("reports") / "healthcare_quality_brief.md"

INTRO = (
    "This is care-gap monitoring on public survey data: a measure-inspired look at who meets the laboratory "
    "criterion for diabetes but has not been told they have it. It is not a certified HEDIS measure, it uses no "
    "protected health information, and it is not clinical guidance."
)

DECISION_QUESTION = (
    "If a health system builds a diabetes screening model or plans screening outreach, does labelling people by "
    "\"a doctor told them\" versus \"their HbA1c meets the ADA criterion\" change who is missed and who is "
    "over-flagged, and where does the undiagnosed gap concentrate?"
)

CANNOT_ESTABLISH = [
    "**Why the gap exists.** Access to care, screening frequency, insurance, clinician behavior and measurement can all produce it, and this survey cannot separate them. Nothing here shows clinician bias.",
    "**A causal effect of anything.** The estimates are descriptive and cross-sectional.",
    "**Local rates.** The estimates describe the US civilian non-institutionalized population, not a health system's patients.",
    "**Clinical correctness of either label.** HbA1c is one of three ADA criteria, fasting glucose is not used, and HbA1c can read high in some people with sickle cell trait.",
    "**Readiness of any model.** The models are minimal comparisons of two labels, not clinical risk models, and none has been validated for deployment.",
    "**Anything about a specific person.** No respondent-level result is reported.",
]

NEXT_ANALYSIS = [
    "Repeat the estimate with the same definitions on the next NHANES cycle to see whether the gap persists.",
    "Run the same definitions on local EHR or claims data, with a governed extract, to size the gap for the health system's own population and to test whether the HbA1c label behaves the same way.",
    "Add fasting glucose as a second criterion, with the fasting-subsample weight, to test how much of the gap depends on using HbA1c alone.",
    "Before any screening workflow changes, pair the false-positive burden with local follow-up capacity so that the cost of over-flagging is known.",
]


def _outreach(t: dict[str, pd.DataFrame], config: Config) -> list[str]:
    est = t["undiagnosis_estimates"].set_index("group")
    summary = t["group_summary"].set_index("group_name")
    overall = est.loc[ALL]
    groups = [g for g in config.groups if not bool(est.loc[g, "small_n_warning"])]
    high = max(groups, key=lambda g: est.loc[g, "estimate"])
    low = min(groups, key=lambda g: est.loc[g, "estimate"])
    cost = t["specificity_cost"]
    comparison = str(config.analysis("comparison_group"))
    race_black = _row(cost, model=RACE, group=comparison)
    diff = t["auc_difference"].set_index("model")
    people = summary.loc[ALL, "weighted_undiagnosed"]
    fpr_diag = 1 - race_black.specificity_diagnosed
    fpr_hba = 1 - race_black.specificity_hba1c
    return [
        f"- **Size of the gap.** An estimated {millions(people)} people ({pct(overall.estimate)}, 95% CI "
        f"{span(overall.ci_low_logit, overall.ci_high_logit)}) of the {millions(overall.weighted_denominator)} "
        "who meet the HbA1c criterion had not been told they have diabetes.",
        f"- **Where to look first.** Among groups without a small-sample warning, the estimated undiagnosed share is "
        f"highest for {high} ({pct(est.loc[high, 'estimate'])}, {span(est.loc[high, 'ci_low_logit'], est.loc[high, 'ci_high_logit'])}) "
        f"and lowest for {low} ({pct(est.loc[low, 'estimate'])}, {span(est.loc[low, 'ci_low_logit'], est.loc[low, 'ci_high_logit'])}). "
        "Intervals for most groups overlap, and only the Black versus White comparison was named in advance, "
        "so the other groups are a prompt for monitoring, not a ranking.",
        f"- **What outreach would need.** Monitoring screening reach and follow-up in groups with a higher estimated "
        f"undiagnosed share, using local data and the same definitions, is the supported next step. Roughly {millions(people)} "
        "is a national estimate, not a local target.",
        f"- **Cost of the label choice.** With race excluded, the two labels give nearly the same ranking "
        f"(AUC {diff.loc[PRIMARY, 'auc_diagnosed_label']:.3f} and {diff.loc[PRIMARY, 'auc_hba1c_label']:.3f}). "
        f"With race included, training on the HbA1c label moves the false-positive rate for {comparison} respondents "
        f"from {pct(fpr_diag)} to {pct(fpr_hba)} ({pp(race_black.cost)}, 95% CI {pp_span(race_black.ci_low, race_black.ci_high)}), "
        "which is extra outreach workload for people without the condition. That is a reason to quantify both labels by group before swapping one for the other.",
    ]


def _glossary(dictionary: dict) -> str:
    rows = [[m["name"], m["definition"], m["unit"]] for m in dictionary["metrics"]]
    return md_table(["Metric", "Definition", "Unit"], rows)


def render_brief(config: Config) -> str:
    t = load_tables(config)
    run = json.loads((config.root / "outputs" / "run_manifest.json").read_text(encoding="utf-8"))
    dictionary = yaml.safe_load((config.root / "configs" / "metric_dictionary.yml").read_text(encoding="utf-8"))
    counts = run["sample_counts"]
    headline = block_headline(t, config)
    lines = [
        "# Healthcare quality brief: diabetes care-gap monitoring, NHANES 2017-2018",
        "",
        f"Generated by `nhanes-diabetes report` from `outputs/tables` on {str(run['generated_at'])[:10]}. "
        "Every number below is read from a generated table. None is typed by hand.",
        "",
        INTRO,
        "",
        "## Decision question",
        "",
        DECISION_QUESTION,
        "",
        "## Population and exclusions",
        "",
        f"{int(counts['analysis_cohort']):,} of {int(counts['participants']):,} NHANES 2017-2018 participants form the analysis cohort. "
        f"It represents {' '.join(str(dictionary['population']).split())}. The steps below show how each exclusion changes the count.",
        "",
        block_cohort_flow(t, config),
        "",
        "Refused and do-not-know answers count as missing, never as \"no\". Weights, strata and PSUs are used for every estimate.",
        "",
        "## Three computed findings, with uncertainty",
        "",
        headline,
        "",
        "## What this means for screening outreach",
        "",
        *_outreach(t, config),
        "",
        "## What the data cannot establish",
        "",
        *[f"- {item}" for item in CANNOT_ESTABLISH],
        "",
        "## Recommended next analysis",
        "",
        *[f"{i}. {item}" for i, item in enumerate(NEXT_ANALYSIS, start=1)],
        "",
        "## Metric glossary",
        "",
        _glossary(dictionary),
        "",
        "## Where each number comes from",
        "",
        "Tables: `outputs/tables/*.csv`. Workbook with live reconciliation formulas: `excel/nhanes_diabetes_quality_review.xlsx`. "
        "Offline dashboard: `dashboard/index.html`. Methods: `docs/methods.md`. Governance: `docs/privacy_and_governance.md`.",
        "",
    ]
    return "\n".join(lines)


def write_brief(config: Config) -> Path:
    path = config.root / BRIEF
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_brief(config), encoding="utf-8")
    return path


def check_brief(config: Config) -> list[str]:
    path = config.root / BRIEF
    if not path.exists():
        return [f"{BRIEF} is missing"]
    if path.read_text(encoding="utf-8") != render_brief(config):
        return [f"{BRIEF} does not match outputs/tables"]
    return []
