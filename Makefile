.PHONY: setup data cohort analyze crosscheck report excel dashboard all lint typecheck test check-readme clean

setup:
	uv sync --extra dev

data:
	uv run python -m nhanes_diabetes download

cohort:
	uv run python -m nhanes_diabetes build-cohort

analyze:
	uv run python -m nhanes_diabetes analyze

crosscheck:
	uv run python -m nhanes_diabetes crosscheck

report:
	uv run python -m nhanes_diabetes report

excel:
	uv run python scripts/build_excel_workbook.py

dashboard:
	uv run python -m nhanes_diabetes dashboard

all:
	uv run python -m nhanes_diabetes all

lint:
	uv run ruff check src tests scripts

typecheck:
	uv run mypy

test: lint typecheck
	uv run pytest --cov=nhanes_diabetes --cov-report=term-missing:skip-covered

check-readme:
	uv run python -m nhanes_diabetes report --check

clean:
	rm -rf data/processed/*.duckdb data/processed/*.csv outputs/tables outputs/figures outputs/run_manifest.json
