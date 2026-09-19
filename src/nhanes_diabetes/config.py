"""Typed access to configs/analysis.yml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG = Path("configs/analysis.yml")


@dataclass(frozen=True)
class Config:
    raw: dict[str, Any]
    root: Path

    @property
    def base_url(self) -> str:
        return str(self.raw["data"]["base_url"])

    @property
    def files(self) -> dict[str, list[str]]:
        return {name: list(cols) for name, cols in self.raw["data"]["files"].items()}

    @property
    def raw_dir(self) -> Path:
        return self.root / self.raw["data"]["raw_dir"]

    @property
    def processed_dir(self) -> Path:
        return self.root / self.raw["data"]["processed_dir"]

    @property
    def manifest_path(self) -> Path:
        return self.root / self.raw["data"]["manifest"]

    @property
    def tables_dir(self) -> Path:
        return self.root / "outputs" / "tables"

    @property
    def figures_dir(self) -> Path:
        return self.root / "outputs" / "figures"

    @property
    def database(self) -> Path:
        return self.processed_dir / "nhanes.duckdb"

    @property
    def sql_dir(self) -> Path:
        return self.root / "sql"

    def analysis(self, key: str) -> Any:
        return self.raw["analysis"][key]

    def validation(self, key: str) -> Any:
        return self.raw["validation"][key]

    @property
    def groups(self) -> list[str]:
        return list(self.raw["analysis"]["group_order"])

    @property
    def lonely_psu(self) -> str:
        return str(self.raw.get("lonely_psu", "fail"))


def load_config(path: Path | str | None = None, root: Path | str | None = None) -> Config:
    base = Path(root) if root else Path.cwd()
    config_path = Path(path) if path else base / DEFAULT_CONFIG
    with config_path.open(encoding="utf-8") as handle:
        return Config(yaml.safe_load(handle), base)
