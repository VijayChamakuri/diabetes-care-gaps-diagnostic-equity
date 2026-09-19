# Calculated fields and parameters

Create these in Tableau after connecting `data/care_gap_summary.csv` and `data/model_tradeoffs.csv`. Rates in the extracts are on a 0 to 1 scale; format them as percentages in Tableau.

## care_gap_summary.csv

| Field | Formula | Note |
|---|---|---|
| `Undiagnosed Share Check` | `SUM([weighted_undiagnosed]) / SUM([weighted_denominator])` | Must equal `[undiagnosed_share]` for a single group. Use it to confirm the extract, never as the plotted value. |
| `Share Label` | `STR(ROUND(SUM([undiagnosed_share]) * 100, 1)) + '% (' + STR(ROUND(SUM([ci_low]) * 100, 1)) + '% to ' + STR(ROUND(SUM([ci_high]) * 100, 1)) + '%)'` | Tooltip text. Use a group filter so each mark is one row. |
| `Is Small Sample` | `[small_sample_warning] = 'SMALL SAMPLE'` | Drives hatching, a lighter color and the footnote. |
| `Is Confirmatory` | `[analysis_type] = 'confirmatory'` | Only the pre-specified comparison. |
| `Difference (pp)` | `SUM([difference_vs_reference]) * 100` | Percentage points. |

Use `ci_low` and `ci_high` as error bars. Never draw a group without its interval.

## model_tradeoffs.csv

Every worksheet filters `metric` to one value, because the extract is long format.

| Field | Formula | Note |
|---|---|---|
| `Estimate (pct)` | `SUM([estimate]) * 100` | Use for sensitivity, specificity, false_positive_rate, ppv, npv and specificity_cost. |
| `AUC` | `IF [metric] = 'auc' THEN [estimate] END` | Not a percentage. |
| `Is Primary Model` | `[model_role] = 'primary'` | Default the model filter to the primary model. |
| `Label Pair` | `IF [label] = 'diagnosed minus hba1c_pos' THEN 'Paired difference' ELSE [label] END` | Groups marks in the legend. |

## Parameters

| Parameter | Type | Values | Use |
|---|---|---|---|
| `Model` | String | The values of `model` | Filter on every page-two worksheet; default is the primary model. |
| `Metric` | String | sensitivity, specificity, false_positive_rate, ppv, npv | Selects the metric on the subgroup worksheet. |

## Rules

- A metric is never shown without its `ci_low` and `ci_high` unless the extract has none (weighted people counts, cohort counts).
- Every group with `small_sample_warning = SMALL SAMPLE` carries a visible marker.
- Exploratory comparisons are labelled with `review_label`, never as findings.
