# QA checklist

Complete every item in Tableau before any document claims a Tableau version. Record the date and the person who checked.

## Data

- [ ] Row counts match `field_dictionary.md` for each extract.
- [ ] Every KPI worksheet reproduces its value in `expected_kpis.csv` to the displayed precision.
- [ ] `Undiagnosed Share Check` equals `undiagnosed_share` for every group.
- [ ] No extract contains a respondent-level field. The only grain is group, model, label, metric or cohort step.

## Design

- [ ] The banner appears on every page.
- [ ] Every rate, share and difference shows its interval, except counts.
- [ ] Every SMALL SAMPLE group is visibly marked.
- [ ] Exploratory comparisons carry their `review_label`; only the pre-specified comparison is called confirmatory.
- [ ] Axes, units and percentage formats are labelled. Percentage points are not labelled as percent.
- [ ] Colors remain distinguishable in grayscale.

## Claims

- [ ] No text says the gap proves clinician bias, causes anything or supports deployment.
- [ ] No text calls the metrics certified HEDIS.
- [ ] Filters and actions work, and the workbook opens without a missing-file warning.

## Publishing

- [ ] The `.twbx` or Tableau Public URL is recorded in `README.md` in this folder.
- [ ] The main README states which artifact is HTML and which is Tableau.
