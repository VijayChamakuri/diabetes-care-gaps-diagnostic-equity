# Privacy and governance

This project analyses public NHANES 2017-2018 files. Nothing here is a health-system data product, and the controls below separate what this repository does from what a production version would need.

## What this data is

- **Public research data.** NHANES is a National Center for Health Statistics survey. The public-use files are released for research and carry no direct identifiers. They are not an EHR extract, a claims feed or a clinical registry.
- **No PHI.** No protected health information is used, stored or published. The raw files are downloaded from CDC at run time, verified by SHA-256 against a manifest and are never committed.
- **No respondent-level output.** Every table, the dashboard, the workbook, the brief and the Tableau extracts hold group, model or check summaries. The workbook and the Tableau extracts are tested for the absence of respondent identifiers.

## Controls a production version would need

None of these is implemented here, because there is nothing to protect beyond public data. They are listed so the design is not mistaken for a deployable one.

| Control | In this repository | In a production setting |
|---|---|---|
| Minimum necessary | Only the seven public files and the columns listed in `configs/analysis.yml` are read. A missing or unexpected column stops the run. | Request only the fields the measure needs, and document why each one is needed. |
| Role-based access | Not applicable to public data. | Separate roles for data engineers, analysts and report consumers. Row-level extracts limited to the smallest group. |
| Audit logging | `outputs/run_manifest.json` records code commit, package versions, seed, file hashes and counts for each run. | Log who queried which extract and when, retain the log and review it. |
| Approved access and disclosure | Data is public. | A data use agreement or governance approval before any extract leaves its source system, and a review before any table is shared. |
| Retention | Raw files and the DuckDB database are git-ignored and rebuilt from source. | A written retention period and secure deletion of extracts and intermediate files. |
| Suppression | Groups are flagged, not hidden (see below). | Disclosure suppression of small counts, set by the data owner. |

## Small-cell handling

- **Reliability flag, not suppression.** A group with fewer than 30 respondents, or a Kish effective sample size under 30, is labelled SMALL SAMPLE in the README, dashboard, workbook and Tableau extract, and its interval is reported so the uncertainty is visible. The pooled Other/Multiracial category is the group affected in this analysis, and it is labelled a pooled category rather than a population.
- **Why counts are not suppressed here.** The counts describe public survey groups and cannot identify a person. A production policy would go further and suppress or combine counts below a disclosure threshold chosen by the data owner. For example, some public health data releases suppress counts from 1 to 10. This repository does not claim to apply any such policy.
- **No individual-level cells.** Tables are never broken down further than race and ethnicity group, model and label.

## Race in the analysis

- **Excluded from the primary model.** The primary model uses age and sex only, so the benchmark does not use race as a predictor.
- **Retained for audit reporting.** Race and ethnicity remain the grouping variable for the undiagnosis estimates and for every subgroup performance table, because the purpose is to see whether performance differs by group.
- **Race-included models are sensitivity analyses.** Using race as a model input while auditing by race needs explicit justification, so those results are reported separately and are not offered as a recommended model.

## How to read the findings

- **Descriptive.** The estimates describe a national survey. They do not show why a gap exists and they are not causal.
- **Not clinical guidance.** The models compare two training labels. They are not clinical risk models and are not ready for deployment.
- **Not a certified measure.** This is care-gap monitoring inspired by quality measurement. It is not a certified HEDIS measure and it makes no claim about any health system's performance.
