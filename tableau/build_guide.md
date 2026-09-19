# Build guide

Build three pages that mirror the offline HTML dashboard. The workbook is not built here, so this guide is a specification, not a record of work done.

Banner on every page, pinned at the top as a text object: `NHANES 2017-2018 public survey data. Descriptive care-gap monitoring, not a certified quality measure and not clinical guidance.`

Use a colorblind-safe palette and label every axis. Put group names on the axis, not only in a legend.

## Page 1: Care gap overview (`care_gap_summary.csv`)

- **KPI tiles.** Undiagnosed share, weighted people undiagnosed, and the pre-specified difference, each read from the All groups row (`is_all_groups = true`) and shown with its interval.
- **Bar chart with error bars.** `undiagnosed_share` by `group` with `ci_low` and `ci_high`. Sort by the estimate and mark `Is Small Sample` groups with a lighter fill and a footnote.
- **Comparison table.** `difference_vs_reference`, its interval, `ratio`, `p_value_holm` and `review_label`. Only the pre-specified row is called confirmatory.
- **Tooltip.** Group, `Share Label`, `hba1c_positive_respondents`, `effective_n_kish`, warning flag.

## Page 2: Model tradeoffs (`model_tradeoffs.csv`)

- **Model and metric filters** using the parameters in `calculated_fields.md`.
- **Dot plot with intervals.** Sensitivity or specificity by `group`, colored by `label`, for the selected model.
- **False-positive burden.** `specificity_cost` by `group` for the primary and the race-included model side by side, with intervals and a zero reference line.
- **AUC strip.** `auc` and `auc_difference` for each model with intervals. State on the page that both labels are scored against the HbA1c criterion.

## Page 3: Methods and data (`cohort_flow.csv`)

- **Cohort waterfall.** `remaining` by `step`, labelled with `criterion` and `removed`.
- **Definitions panel.** Text object with the denominators and the limitations from `../docs/methods.md` and `../docs/privacy_and_governance.md`.
- **Source note.** CDC NHANES 2017-2018 with the file list from `../data/data_manifest.json`.

## Interactions

- Filter action from the Page 1 bar chart to the Page 2 group selection.
- A group filter that applies to every worksheet on Pages 1 and 2.

## Before publishing

Complete `qa_checklist.md`. Do not publish a workbook that has not passed it.
