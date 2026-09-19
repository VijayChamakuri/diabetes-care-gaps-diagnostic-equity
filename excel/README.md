# Excel quality review

`nhanes_diabetes_quality_review.xlsx` is a seven-sheet review of the NHANES 2017-2018 diabetes care-gap analysis. It is built by [`scripts/build_excel_workbook.py`](../scripts/build_excel_workbook.py) (or `make excel`) from the pipeline's CSV and JSON outputs. No value is typed by hand, and no respondent-level rows are included.

| Sheet | Contents |
|---|---|
| `Executive_Summary` | Five decision metrics with intervals, unweighted and effective n, definitions, source table, refresh date, population, limitations and a reconciliation status for every sheet |
| `Cohort_Flow` | Starting sample, each exclusion, the final cohort, counts by group and a reconciliation table |
| `Care_Gaps` | Weighted undiagnosed share with a 95% interval, unweighted n, effective n and a small-sample flag for each group |
| `Subgroup_Review` | Each group against the reference with difference, ratio, p-value, Holm-adjusted p-value and an exploratory label |
| `Model_Tradeoffs` | AUC by model and label, sensitivity, specificity and false-positive rate by group with intervals, and the false-positive burden of the HbA1c label |
| `Data_Quality` | Pipeline checks, missingness by group, duplicate and validity checks, source file hashes and the R cross-check |
| `Metric_Dictionary` | Numerator, denominator, exclusions, unit and source for every metric |

## Reading the workbook

- Values come from `outputs/tables`. Rates, interval widths, false-positive rates, variance checks and every PASS or FAIL status are live formulas, so a reviewer can see and change them.
- Cells labelled `SMALL SAMPLE` are highlighted yellow. A failed check turns red, and every sheet's checks roll up on the summary sheet.
- Every sheet has an Excel table with filters and frozen headers. Percentages are stored as fractions and formatted as percentages; differences are in percentage points.
- Calculated results are stored with the formulas so previewers that do not calculate still show them. Excel recalculates when the file is opened.

## Verification

`tests/test_excel_workbook.py` checks the sheet list, the banner on every sheet, the absence of respondent-level fields, every displayed value against the generated CSVs, and every formula with an independent formula engine. `make check-readme` also fails when the committed workbook no longer matches `outputs/tables`.

This is descriptive care-gap monitoring on public survey data, not a certified quality measure and not clinical guidance.
