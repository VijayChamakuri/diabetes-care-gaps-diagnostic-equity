# Contributing

```bash
uv sync --extra dev        # environment from the lockfile
make test                  # ruff, mypy, pytest with coverage
make check-readme          # README numbers must match outputs/tables
uv run python -m nhanes_diabetes all
```

Requires Python 3.11 or 3.12 and `uv`. R with the `survey` package is optional; without it the cross-check is skipped locally and in the fast CI job.

- Every number in the README lives in a generated block. Change `src/nhanes_diabetes/report.py` and rerun `nhanes-diabetes report`, never edit a block by hand.
- Cohort rules belong in `sql/`, not in Python.
- A new estimate needs a test with a known answer, and a comparison with R if it is a survey estimator.
- Never commit raw NHANES files or anything under `data/raw`.
- Analyses other than the pre-specified contrast are labelled exploratory.
