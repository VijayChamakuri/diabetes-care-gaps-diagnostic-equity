# Methods

## Question and estimands

1. **Undiagnosis share.** Among respondents whose HbA1c is 6.5% or higher, the weighted share who answered no to "a doctor told you that you have diabetes". This is a descriptive estimate for the US civilian non-institutionalized population aged 12 and older with valid data. The pre-specified confirmatory contrast is Non-Hispanic Black against Non-Hispanic White.
2. **Label comparison.** Two models with identical inputs, one trained on `diagnosed` and one on `hba1c_pos`, both scored against the HbA1c criterion. The estimands are the AUC difference, the specificity cost (specificity of the diagnosed-label model minus the HbA1c-label model), and the sensitivity gap against the reference group.

## Weights and design

- **Weight: `WTMEC2YR`.** Every variable used (demographics, the diabetes questionnaire, HbA1c, BMI, insurance, family history, routine care) comes from the interview or the mobile examination center, so the exam weight is the correct one. `WTSAF2YR` (the fasting subsample weight) is only needed for fasting glucose. Fasting glucose is not part of the question, so `GLU_J` is no longer downloaded or merged.
- **Strata and PSUs:** `SDMVSTRA` and `SDMVPSU` (masked variance units). With two PSUs in each of 15 strata, the full design has 15 degrees of freedom.
- **Subpopulations.** A group is estimated as a domain of the full design: the indicator is zero outside the group and every stratum and PSU stays in the variance. Analysing a group as if it were its own survey drops PSUs and understates variance.
- **Variance.** Taylor linearization of the weighted ratio, stratified with-replacement PSU estimator, no finite-population correction.
- **Degrees of freedom.** PSUs with positive domain weight minus strata with positive domain weight, as in `survey::degf`.
- **Interval method.** Proportions use the logit interval with a t quantile on those degrees of freedom (`svyciprop(method = "logit")`). Wald intervals are in `outputs/tables/undiagnosis_estimates.csv`. Logit is used in the README because it stays inside 0 to 1 and behaves better for small groups.
- **Lonely PSUs.** The pipeline stops if any stratum has one PSU (`lonely_psu: fail`). `centered` and `remove` are available in the config for other data.
- **Effective sample size.** Kish effective n from the weights, and a design-based value from the variance, are reported next to every proportion. Small-sample warnings use fewer than 30 respondents or an effective n under 30.

## Group comparisons

Differences and ratios use a joint linearization, so the shared PSUs between two groups are accounted for. Treating two groups as independent misstates the standard error, which is why the Black minus White standard error matches R's `svycontrast` and not the square root of the summed variances.

Only Black against White was named in advance. The other four comparisons with the reference group are exploratory and reported with Holm-adjusted p-values. Nothing is claimed from an exploratory comparison alone.

Age-standardized estimates use direct standardization to the age mix of everyone meeting the criterion, with a linearized variance. The table flags groups whose mean age differs from the reference by more than five years.

## Models

| Model | Inputs | Role |
|---|---|---|
| `demographic_logistic` | age, sex | Primary benchmark, race excluded |
| `demographic_race_logistic` | age, sex, race dummies | Sensitivity |
| `extended_logistic` | adds BMI, family history, insurance, routine care place | Sensitivity, race excluded |
| `extended_boosting` | same inputs, gradient boosting | Comparison: does nonlinearity add decision value |

- **Race is excluded from the primary models** because using race as a predictor while auditing performance by race needs explicit justification. Race-included versions are sensitivity analyses.
- **HbA1c is never an input.** It defines one of the labels.
- **Availability.** Age, sex, insurance and routine care place are known before any diagnosis. BMI is measured at the same exam as HbA1c but is not part of the outcome definition. Family history is only asked of adults 20 and older; it is imputed with a missing indicator.
- **Access-to-care inputs are part of the diagnostic process.** Their presence in the extended model means it is describing who gets diagnosed, not only who has disease. That is the point of the audit, and it is why the extended model is not offered as a clinical tool.
- **Weights in fitting** are rescaled to mean one so the L2 penalty keeps a stable meaning.

## Validation

- **Repeated stratified grouped cross-validation.** Folds are grouped by stratum and PSU so respondents from one PSU never sit on both sides of a split, and stratified by the HbA1c outcome. A test proves that a label fixed per cluster cannot be learned across folds.
- **Nested threshold.** The Youden threshold (weighted sensitivity plus specificity minus one) is chosen from inner out-of-fold predictions on the training clusters only, then applied unchanged to the held-out fold.
- **Uncertainty.** A Rao-Wu rescaled bootstrap draws one PSU from each two-PSU stratum and doubles its weight. Drawing both PSUs, as a naive bootstrap does, understates the variance by half. Percentile intervals come from bootstrap replicates of the metrics computed on the fixed out-of-fold predictions.
- **What the bootstrap does not include.** Refitting variability. Intervals reflect survey-design sampling variability of the evaluation, not of the fitted model.
- **AUC difference.** A paired bootstrap on the same replicates gives the interval and p-value for the difference. Overlapping intervals are not used to infer indistinguishability.
- **Subgroup metrics.** Sensitivity, specificity, PPV and NPV with intervals, positive counts and effective n. A group with fewer than 30 positives or an effective n under 30 carries a warning.
- **Calibration.** Equal-population weighted bins and weighted Brier scores by group, each model against its own label.

## Does this answer the policy question?

Both models are scored against the HbA1c criterion, but they were trained on different labels. That answers "if I deploy a model trained on this label, how does it perform against a biochemical standard, and for whom". It does not answer whether either label is the right target for care: HbA1c is one of three ADA criteria, is affected by conditions such as sickle cell trait, and is only measured in people who attended an exam. The comparison is evidence about label choice, not about clinical correctness.

## Missing data and robustness

- Refused and do-not-know answers are missing, never "no".
- Missingness by group is reported. A complete-case sensitivity analysis restricts the undiagnosis contrast to respondents with every extended input observed.
- Other definitions: borderline answers counted as diagnosed or as not diagnosed, and adults only.
- Alternative biochemical definitions were not added because they were not pre-specified.

## Corrections to the first version

The first version was a single script. Rebuilding it as a pipeline changed or corrected these results:

| First version | Now |
|---|---|
| Analysis sample of 5,877 | 5,873. Four "do not know" answers to the diabetes question had been counted as "not diagnosed" |
| Black minus White difference tested as independent groups, p = 0.0055 | Joint linearization and 15 degrees of freedom, p = 0.0045. The difference and ratio are unchanged |
| M1 AUC reported as 0.763 | The script printed 0.742, and it was scored against the diagnosed label, not the HbA1c criterion as the text said |
| AUC intervals from a naive PSU bootstrap | Rao-Wu rescaled bootstrap. The old M1 interval did not contain its own point estimate |
| Specificity cost of +16.4 pp for Black respondents from one 70/30 split, race included | With race excluded the overall cost is +0.7 pp and no group's interval excludes zero. With race included, the cost is +10.0 pp for Black respondents and -1.9 pp for White respondents |
| Sensitivity shown as point estimates, one at 100% for a small group | Intervals, positive counts, effective n and small-sample warnings for every group |
| Charts not generated by any code in the repository | Generated by `nhanes-diabetes report`, on a full 0 to 100 axis or as dot-and-interval plots |
| README numbers typed by hand | Generated from `outputs/tables` and checked in CI |
| `GLU_J` merged but unused, `WTSAF2YR` loaded | Removed |
