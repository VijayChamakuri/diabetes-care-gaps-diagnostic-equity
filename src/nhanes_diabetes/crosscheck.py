"""Compare the Python survey estimators with R's ``survey`` package."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd

from nhanes_diabetes.config import Config
from nhanes_diabetes.survey import Design, contrast, estimate_mean

TOLERANCE = 1e-6
CONTRAST_LABEL = "Non-Hispanic Black minus Non-Hispanic White"


def r_survey_available() -> bool:
    rscript = shutil.which("Rscript")
    if not rscript:
        return False
    done = subprocess.run(
        [rscript, "-e", 'quit(status = !requireNamespace("survey", quietly = TRUE))'],
        capture_output=True, check=False)
    return done.returncode == 0


def python_estimates(cohort: pd.DataFrame, config: Config) -> pd.DataFrame:
    design = Design.from_frame(cohort, lonely=config.lonely_psu)
    pos = (cohort["hba1c_pos"] == 1).to_numpy()
    y = 1.0 - cohort["diagnosed"].to_numpy(dtype=float)
    rows = []
    for name, dom in [("All groups", np.ones(len(cohort), dtype=bool))] + [
        (g, (cohort["race_label"] == g).to_numpy()) for g in sorted(cohort["race_label"].unique())
    ]:
        e = estimate_mean(design, y, pos & dom)
        rows.append({"group": name, "estimate": e.estimate, "se": e.se, "df": e.df,
                     "ci_low_logit": e.ci_logit[0], "ci_high_logit": e.ci_logit[1],
                     "ci_low_wald": e.ci_wald[0], "ci_high_wald": e.ci_wald[1]})
    black, white = "Non-Hispanic Black", "Non-Hispanic White"
    c = contrast(design, y, pos & (cohort["race_label"] == black).to_numpy(),
                 pos & (cohort["race_label"] == white).to_numpy())
    rows.append({"group": CONTRAST_LABEL, "estimate": c.difference, "se": c.se, "df": c.df,
                 "ci_low_logit": np.nan, "ci_high_logit": np.nan, "ci_low_wald": np.nan, "ci_high_wald": np.nan})
    return pd.DataFrame(rows)


def compare(py: pd.DataFrame, r: pd.DataFrame, tolerance: float = TOLERANCE) -> pd.DataFrame:
    merged = py.merge(r, on="group", suffixes=("_python", "_r"), validate="1:1")
    rows = []
    for quantity in ("estimate", "se", "df", "ci_low_logit", "ci_high_logit", "ci_low_wald", "ci_high_wald"):
        for _, row in merged.iterrows():
            a, b = row[f"{quantity}_python"], row[f"{quantity}_r"]
            if pd.isna(a) and pd.isna(b):
                continue
            diff = abs(float(a) - float(b)) if not (pd.isna(a) or pd.isna(b)) else float("nan")
            rows.append({"quantity": quantity, "group": row["group"], "python": a, "r": b,
                         "absolute_difference": diff, "tolerance": tolerance,
                         "status": "pass" if diff <= tolerance else "FAIL"})
    return pd.DataFrame(rows)


def run_crosscheck(config: Config, require_r: bool = True) -> pd.DataFrame | None:
    if not r_survey_available():
        if require_r:
            raise RuntimeError("Rscript with the 'survey' package is required. Install with "
                               "install.packages('survey') or use --skip-if-no-r.")
        return None
    cohort_path = config.processed_dir / "cohort.csv"
    r_path = config.tables_dir / "r_estimates.csv"
    subprocess.run(["Rscript", str(config.root / "r" / "validation.R"), str(cohort_path), str(r_path)],
                   check=True)
    result = compare(python_estimates(pd.read_csv(cohort_path), config), pd.read_csv(r_path))
    result.to_csv(config.tables_dir / "r_python_crosscheck.csv", index=False)
    return result
