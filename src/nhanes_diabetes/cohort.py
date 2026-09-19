"""Load raw NHANES tables into DuckDB and build the analysis cohort with SQL."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pyreadstat

from nhanes_diabetes.config import Config
from nhanes_diabetes.download import local_path

RAW_TABLES = {
    "DEMO_J": "raw_demo",
    "DIQ_J": "raw_diq",
    "GHB_J": "raw_ghb",
    "BMX_J": "raw_bmx",
    "MCQ_J": "raw_mcq",
    "HIQ_J": "raw_hiq",
    "HUQ_J": "raw_huq",
}


class CohortError(RuntimeError):
    """Cohort construction or a data-quality gate failed."""


@dataclass(frozen=True)
class Variant:
    """One analysis definition. The default is the pre-specified main analysis."""

    name: str = "main"
    borderline: str = "exclude"  # exclude | positive | negative
    min_age: int = 0

    def params(self, hba1c_threshold: float) -> dict[str, Any]:
        include = self.borderline in ("positive", "negative")
        return {
            "min_age": self.min_age,
            "borderline_include": include,
            "borderline_value": 1 if self.borderline == "positive" else 0,
            "hba1c_threshold": hba1c_threshold,
        }


@dataclass(frozen=True)
class Cohort:
    data: pd.DataFrame
    attrition: pd.DataFrame
    quality: pd.DataFrame
    variant: Variant


def _register(con: duckdb.DuckDBPyConnection, table: str, frame: pd.DataFrame) -> None:
    frame = frame.copy()
    frame.columns = [column.lower() for column in frame.columns]
    con.register("_frame", frame)
    con.execute(f"create or replace table {table} as select * from _frame")
    con.unregister("_frame")
    # pandas NaN becomes DuckDB NaN, which compares greater than every number. Use NULL.
    for column, dtype in zip(frame.columns, frame.dtypes, strict=True):
        if dtype.kind == "f":
            con.execute(f'update {table} set "{column}" = null where isnan("{column}")')


def load_raw(con: duckdb.DuckDBPyConnection, config: Config) -> dict[str, int]:
    counts = {}
    for name, table in RAW_TABLES.items():
        frame, _ = pyreadstat.read_xport(str(local_path(config, name)))
        columns = [c for c in frame.columns if c.upper() in {x.upper() for x in config.files[name]}]
        _register(con, table, frame[columns])
        counts[name] = len(frame)
    return counts


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path, params: dict[str, Any]) -> None:
    """Execute every statement in a SQL file with the same named parameters."""
    text = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                     if not line.strip().startswith("--"))
    for statement in (part.strip() for part in text.split(";")):
        if statement:
            used = {key: value for key, value in params.items() if f"${key}" in statement}
            con.execute(statement, used)


def build_cohort(
    con: duckdb.DuckDBPyConnection, config: Config, variant: Variant | None = None
) -> Cohort:
    variant = variant or Variant()
    params = variant.params(float(config.analysis("hba1c_threshold")))
    for name in ("cohort.sql", "data_quality.sql", "cohort_validation.sql", "group_summary.sql"):
        run_sql_file(con, config.sql_dir / name, params)
    quality = pd.concat(
        [
            con.execute("select 'data_quality' as suite, * from data_quality").df(),
            con.execute("select 'cohort_validation' as suite, * from cohort_validation").df(),
        ],
        ignore_index=True,
    )
    failed = quality[~quality["passed"]]
    if not failed.empty:
        raise CohortError(f"Data-quality checks failed:\n{failed.to_string(index=False)}")
    return Cohort(
        data=con.execute("select * from cohort order by seqn").df(),
        attrition=con.execute("select * from cohort_attrition order by step").df(),
        quality=quality,
        variant=variant,
    )
