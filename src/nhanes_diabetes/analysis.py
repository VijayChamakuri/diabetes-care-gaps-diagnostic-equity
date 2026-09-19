"""Pipeline stages: build the cohort, run the analysis, write tables and a run manifest."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from nhanes_diabetes import estimates
from nhanes_diabetes.cohort import Cohort, Variant, build_cohort, load_raw
from nhanes_diabetes.config import Config
from nhanes_diabetes.evaluation import evaluate_models
from nhanes_diabetes.survey import Design


def write_tables(directory: Path, tables: dict[str, pd.DataFrame]) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, frame in tables.items():
        path = directory / f"{name}.csv"
        frame.to_csv(path, index=False)
        written[name] = path
    return written


def build(config: Config) -> Cohort:
    """Load raw files into DuckDB, build and check the cohort, and export it for R."""
    config.processed_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(config.database)) as con:
        load_raw(con, config)
        cohort = build_cohort(con, config, Variant())
        summary = con.execute("select * from group_summary order by group_name").df()
    cohort.data.to_csv(config.processed_dir / "cohort.csv", index=False)
    write_tables(config.tables_dir, {
        "cohort_attrition": cohort.attrition,
        "data_quality": cohort.quality,
        "group_summary": summary,
    })
    return cohort


def analyze(config: Config) -> dict[str, pd.DataFrame]:
    """Estimates, contrasts, robustness and model evaluation; returns every table written."""
    with duckdb.connect(str(config.database)) as con:
        cohort = build_cohort(con, config, Variant())
        data = cohort.data
        design = Design.from_frame(data, lonely=config.lonely_psu)
        tables: dict[str, pd.DataFrame] = {
            "undiagnosis_estimates": estimates.undiagnosis_table(data, design, config),
            "undiagnosis_contrasts": estimates.contrast_table(data, design, config),
            "weighted_prevalence": estimates.prevalence_table(data, design, config),
            "baseline_characteristics": estimates.baseline_characteristics(data, design, config),
            "missingness_by_group": estimates.missingness_table(data, config),
            "age_standardized_undiagnosis": estimates.age_standardized_table(data, design, config),
            "robustness": estimates.robustness_table(con, config, data),
        }
    evaluation = evaluate_models(data, design, config)
    tables.update(evaluation.tables)
    write_tables(config.tables_dir, tables)
    return tables


def _git_commit(root: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unavailable"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(config: Config) -> dict[str, object]:
    """Record what produced the outputs: code commit, seed, source hashes, versions, counts."""
    data_manifest = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    attrition = pd.read_csv(config.tables_dir / "cohort_attrition.csv")
    packages = ["numpy", "pandas", "scipy", "scikit-learn", "duckdb", "pyreadstat", "matplotlib"]
    manifest = {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "code_commit": _git_commit(config.root),
        "seed": config.analysis("seed"),
        "python": platform.python_version(),
        "packages": {p: importlib.metadata.version(p) for p in packages},
        "source_files": {k: {"sha256": v["sha256"], "bytes": v["bytes"], "retrieved_at": v["retrieved_at"]}
                         for k, v in data_manifest["files"].items()},
        "sample_counts": {"participants": int(attrition["n"].iloc[0]), "analysis_cohort": int(attrition["n"].iloc[-1])},
        "validation": {k: config.raw["validation"][k] for k in config.raw["validation"]},
        "outputs": {p.name: _sha256(p) for p in sorted(config.tables_dir.glob("*.csv"))},
    }
    (config.root / "outputs" / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
