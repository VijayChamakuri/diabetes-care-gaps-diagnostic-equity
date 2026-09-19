"""Synthetic NHANES-shaped data for tests. Never real NHANES rows."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from nhanes_diabetes.cohort import RAW_TABLES, _register
from nhanes_diabetes.config import Config, load_config

REPO = Path(__file__).resolve().parents[1]
RACES = [1, 2, 3, 4, 6, 7]


def make_config(root: Path, fast: bool = True) -> Config:
    """The real config, rooted in a temp folder that holds a copy of the SQL, with cheap validation."""
    shutil.copytree(REPO / "sql", root / "sql", dirs_exist_ok=True)
    raw = copy.deepcopy(load_config(root=REPO).raw)
    if fast:
        raw["validation"].update({"folds": 3, "repeats": 2, "inner_folds": 2,
                                  "bootstrap_replicates": 40, "auc_bootstrap_replicates": 40})
    return Config(raw, root)


def synthetic_raw(n: int = 1500, seed: int = 3) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    seqn = np.arange(1, n + 1)
    age = rng.integers(12, 81, n).astype(float)
    race = rng.choice(RACES, n, p=[0.15, 0.1, 0.35, 0.2, 0.12, 0.08])
    bmi = np.clip(rng.normal(28, 6, n), 15, 60)
    risk = -6 + 0.05 * age + 0.06 * bmi + 0.4 * (race == 4)
    truth = rng.random(n) < 1 / (1 + np.exp(-risk))
    hba1c = np.where(truth, rng.normal(7.2, 0.8, n), rng.normal(5.4, 0.4, n))
    told = np.where(truth, rng.random(n) < np.where(race == 4, 0.6, 0.85), rng.random(n) < 0.02)
    diq = np.where(told, 1.0, 2.0)
    diq[rng.random(n) < 0.03] = 3.0
    diq[rng.random(n) < 0.004] = 9.0
    demo = pd.DataFrame({
        "SEQN": seqn, "RIDAGEYR": age, "RIAGENDR": rng.integers(1, 3, n).astype(float),
        "RIDRETH3": race.astype(float), "WTMEC2YR": rng.lognormal(10, 0.6, n),
        "SDMVPSU": rng.integers(1, 3, n).astype(float), "SDMVSTRA": (seqn % 8 + 100).astype(float),
    })
    demo.loc[rng.random(n) < 0.05, "WTMEC2YR"] = 0.0
    ghb = pd.DataFrame({"SEQN": seqn, "LBXGH": hba1c})
    ghb.loc[rng.random(n) < 0.25, "LBXGH"] = np.nan
    return {
        "DEMO_J": demo,
        "DIQ_J": pd.DataFrame({"SEQN": seqn, "DIQ010": diq}),
        "GHB_J": ghb,
        "BMX_J": pd.DataFrame({"SEQN": seqn, "BMXBMI": np.where(rng.random(n) < 0.03, np.nan, bmi)}),
        "MCQ_J": pd.DataFrame({"SEQN": seqn, "MCQ300C": rng.choice([1.0, 2.0, 9.0, np.nan], n)}),
        "HIQ_J": pd.DataFrame({"SEQN": seqn, "HIQ011": rng.choice([1.0, 2.0, 7.0], n, p=[0.85, 0.14, 0.01])}),
        "HUQ_J": pd.DataFrame({"SEQN": seqn, "HUQ030": rng.choice([1.0, 2.0, 3.0], n, p=[0.8, 0.1, 0.1])}),
    }


def load_synthetic(con: duckdb.DuckDBPyConnection, frames: dict[str, pd.DataFrame] | None = None) -> None:
    for name, frame in (frames or synthetic_raw()).items():
        _register(con, RAW_TABLES[name], frame)
