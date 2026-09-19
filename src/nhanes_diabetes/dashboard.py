"""Build dashboard/index.html, one offline file, from outputs/tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from nhanes_diabetes.config import Config

TABLES = {
    "undiagnosis": "undiagnosis_estimates",
    "contrasts": "undiagnosis_contrasts",
    "age_standardized": "age_standardized_undiagnosis",
    "robustness": "robustness",
    "attrition": "cohort_attrition",
    "quality": "data_quality",
    "missingness": "missingness_by_group",
    "model_specification": "model_specification",
    "subgroup_metrics": "subgroup_metrics",
    "specificity_cost": "specificity_cost",
    "auc_difference": "auc_difference",
    "thresholds": "thresholds",
}


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(frame.to_json(orient="records", double_precision=10))


def build_payload(config: Config) -> dict[str, Any]:
    payload: dict[str, Any] = {key: _records(pd.read_csv(config.tables_dir / f"{name}.csv"))
                               for key, name in TABLES.items()}
    cross = config.tables_dir / "r_python_crosscheck.csv"
    payload["crosscheck"] = _records(pd.read_csv(cross)) if cross.exists() else []
    attrition = pd.read_csv(config.tables_dir / "cohort_attrition.csv")
    payload["meta"] = {
        "groups": config.groups,
        "reference_group": config.analysis("reference_group"),
        "comparison_group": config.analysis("comparison_group"),
        "min_positives": config.analysis("min_positives"),
        "min_effective_n": config.analysis("min_effective_n"),
        "sample": f"Analysis cohort of {int(attrition['n'].iloc[-1]):,} respondents.",
    }
    return payload


def _inline(text: str) -> str:
    return text.replace("</", "<\\/")


def build_dashboard(config: Config, output: Path | None = None) -> Path:
    folder = config.root / "dashboard"
    template = (folder / "template.html").read_text(encoding="utf-8")
    html = (
        template.replace("/*STYLE*/", (folder / "style.css").read_text(encoding="utf-8"))
        .replace("/*APP*/", _inline((folder / "app.js").read_text(encoding="utf-8")))
        .replace("/*DATA*/", _inline(json.dumps(build_payload(config), separators=(",", ":"), allow_nan=False)))
    )
    target = output or folder / "index.html"
    target.write_text(html, encoding="utf-8")
    return target
