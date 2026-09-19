# Runtime verification

Commands run and what they returned. Environment: macOS on Apple silicon, `uv`, R 4.6.1 with the `survey` package (4.5), DuckDB 1.5.5, pandas 2.3.3, openpyxl 3.1.5. Date: 2026-09-19. All estimates are NHANES 2017-2018 public-use survey data, descriptive and not causal.

## Clean clone, Python 3.11 and 3.12

```bash
git clone <repo> && cd <repo>
UV_PYTHON=3.11 uv sync --extra dev && make test && make check-readme
UV_PYTHON=3.12 uv sync --extra dev && make test && make check-readme
```

| Check | Python 3.11 | Python 3.12 |
|---|---|---|
| `ruff check src tests scripts` | pass | pass |
| `mypy` (19 source files) | pass | pass |
| `pytest --cov` | 82 passed, 96% coverage | 82 passed, 96% coverage |
| `make check-readme` (README blocks, brief, Tableau extracts, workbook values) | match `outputs/tables` | match `outputs/tables` |

## Real-data pipeline from a clean clone

```bash
uv run python -m nhanes_diabetes all
```

| Stage | Result |
|---|---|
| Download and verify | 7 CDC NHANES files verified against `data/data_manifest.json` (schema and SHA-256) |
| Cohort and data quality | 5,873 of 9,254 participants; 14 of 14 SQL data-quality and cohort-validation checks passed |
| Analysis | 17 tables written with the fixed seed |
| R cross-check | 52 of 52 Python estimates match R `survey` within 1e-06 |
| Artifacts | README blocks, quality brief, Tableau extracts, Excel workbook and dashboard regenerated |
| Wall time | about 47 seconds with the raw files freshly downloaded |

Reproducibility: after the run, `git status` showed changes only in files that carry a timestamp or renderer noise (`outputs/run_manifest.json`, the SVG figures and the workbook's metadata). Every table under `outputs/tables`, the README, the brief and the Tableau extracts were byte-identical to the committed versions.

## Excel workbook

| Check | Result |
|---|---|
| Sheets | the seven required sheets, in order |
| Values | every displayed value compared with the generated CSVs and the source manifest by `tests/test_excel_workbook.py` |
| Formulas | 553 formulas recalculated with the independent `formulas` engine: 0 errors, 149 PASS statuses, 7 sheet-level ALL CHECKS PASS |
| Tamper test | changing one estimate in a copy of the tables makes the workbook report FAIL and REVIEW |
| Respondent rows | none; the tests reject respondent-level headers and long tables |
| Visual inspection | all seven sheets rendered and inspected for labels, clipping, formats, warning colors and the banner. Two layout defects found (a wide step column and truncated group names) and fixed |

## Claims audit

The test `test_guarded_terms_only_appear_in_denials` searches the README, docs, brief, workbook guide and Tableau documents for HEDIS, Epic, Clarity, Caboodle, HIPAA, Tableau dashboard, real patient and savings, and fails unless the line contains a denial. Every hit is a denial ("not a certified HEDIS measure", "no Tableau workbook"). No em dashes and no AI attribution appear in the repository.

## Not verified

- No Tableau workbook exists, so nothing was checked in Tableau.
- The alternative HbA1c threshold sensitivity is deferred for lack of a clinical source (see `docs/implementation_status.md`).

## Hosted CI (GitHub Actions)

On the pull request branch, all three jobs passed: lint, types and tests on Python 3.11 and on Python 3.12 (including `make check-readme`), and the real-data job. The real-data job installed R and the `survey` package, downloaded and verified the CDC files, ran the full pipeline including the R cross-check, and `git diff` of the README, the undiagnosis estimates, the R cross-check table and the Tableau extracts against the committed versions was empty. The published numbers therefore reproduce from the CDC files on a clean machine.
