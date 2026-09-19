import json
from pathlib import Path

import pandas as pd
import pyreadstat
import pytest

from nhanes_diabetes.download import DataIntegrityError, download, validate_schema
from tests.fixtures import make_config


def _write(config, name: str, columns: list[str], value: float = 1.0) -> Path:
    path = config.raw_dir / f"{name}.xpt"
    path.parent.mkdir(parents=True, exist_ok=True)
    pyreadstat.write_xport(pd.DataFrame({c: [value, value + 1] for c in columns}), str(path), file_format_version=5)
    return path


def _all(config, value: float = 1.0) -> None:
    for name, columns in config.files.items():
        _write(config, name, columns, value)


def test_schema_check_names_the_missing_column(tmp_path) -> None:
    config = make_config(tmp_path)
    path = _write(config, "GHB_J", ["SEQN"])
    with pytest.raises(DataIntegrityError, match="LBXGH"):
        validate_schema(path, "GHB_J", ["SEQN", "LBXGH"])


def test_manifest_records_hash_size_and_source(tmp_path) -> None:
    config = make_config(tmp_path)
    _all(config)
    manifest = download(config)  # files already present, so nothing is fetched
    entry = manifest["files"]["DEMO_J"]
    assert entry["source_url"].endswith("/DEMO_J.xpt") and len(entry["sha256"]) == 64
    assert entry["bytes"] == (config.raw_dir / "DEMO_J.xpt").stat().st_size
    assert json.loads(config.manifest_path.read_text())["files"].keys() == config.files.keys()


def test_changed_file_fails_until_the_manifest_is_refreshed(tmp_path) -> None:
    config = make_config(tmp_path)
    _all(config)
    first = download(config)
    _all(config, value=5.0)  # CDC "revised" every file
    with pytest.raises(DataIntegrityError, match="does not match the manifest"):
        download(config)
    refreshed = download(config, refresh_manifest=True)
    assert refreshed["files"]["DEMO_J"]["sha256"] != first["files"]["DEMO_J"]["sha256"]
    assert download(config)["files"]["DEMO_J"]["sha256"] == refreshed["files"]["DEMO_J"]["sha256"]
