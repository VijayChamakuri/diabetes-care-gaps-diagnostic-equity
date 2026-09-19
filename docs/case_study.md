# Case study: diabetes care gaps and diagnostic equity

For a recruiter or hiring manager who has five minutes. This page links the pieces; the numbers live in the linked artifacts and are generated from one set of tables, so they cannot disagree.

## The question

If a health system builds a diabetes screening model or plans screening outreach, does the choice of label change who the model misses and who it over-flags? The two labels are "a doctor told them" and "their HbA1c meets the ADA criterion". The related operational question is where the undiagnosed gap concentrates.

## The data

NHANES 2017-2018 public-use files from the National Center for Health Statistics: demographics, the diabetes questionnaire, HbA1c, BMI, insurance, family history and place of routine care. It is a survey with weights, strata and primary sampling units, not an EHR or claims extract. Every source file is downloaded from CDC, hashed and recorded in [`data/data_manifest.json`](../data/data_manifest.json).

## The approach

- A SQL cohort with an attrition table, checked by independent SQL on every run.
- Design-based survey estimation (weights, strata, PSUs), with subgroups treated as subpopulations, checked against R's `survey` package.
- One pre-specified comparison and Holm-adjusted p-values for the exploratory ones.
- Two models with identical inputs and different labels, grouped cross-validation, and a Rao-Wu bootstrap for uncertainty.
- Race excluded from the primary model and kept for audit reporting.

Detail: [methods](methods.md) and [data dictionary](data_dictionary.md).

## Where to look

| If you want | Open |
|---|---|
| The findings with their uncertainty, in decision language | [Quality brief](../reports/healthcare_quality_brief.md) |
| An analyst's workbook with live reconciliation formulas | [Excel quality review](../excel/README.md) |
| The visual overview, offline | [`dashboard/index.html`](../dashboard/index.html) |
| The headline numbers and the reproduction command | [README](../README.md) |
| What is and is not protected | [Privacy and governance](privacy_and_governance.md) |
| Every acceptance criterion and its evidence | [Implementation status](implementation_status.md) |

## What this shows about my work

- Survey-weighted analysis done correctly, with denominators, effective sample sizes and small-sample warnings on every estimate.
- SQL for cohort logic and data quality, Python for estimation, R for an independent check.
- Metric definitions written once ([`configs/metric_dictionary.yml`](../configs/metric_dictionary.yml)) and reused by the workbook, the brief and the Tableau field dictionary.
- Reproducibility: fixed seeds, hash-verified inputs, generated documents and a CI job that fails when a document drifts from the tables.
- Honest scope: descriptive findings, no causal claim, no certified measure, and a Tableau package that says plainly no workbook exists.

## What this does not show

Experience with an EHR, with claims data, with Tableau in production or with a live clinical deployment. The Tableau folder is preparation for a workbook, not a workbook.
