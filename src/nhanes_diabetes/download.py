"""Download NHANES files from CDC, verify integrity and schema, and record provenance."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyreadstat

from nhanes_diabetes.config import Config


class DataIntegrityError(RuntimeError):
    """A downloaded file does not match the recorded manifest or expected schema."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_url(config: Config, name: str) -> str:
    return f"{config.base_url}/{name}.xpt"


def local_path(config: Config, name: str) -> Path:
    return config.raw_dir / f"{name}.xpt"


def _fetch(url: str, target: Path, attempts: int = 3) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "nhanes-diabetes/1.0"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
            if not data:
                raise DataIntegrityError(f"CDC returned an empty file for {url}")
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_suffix(".part")
            partial.write_bytes(data)
            partial.replace(target)
            return
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == attempts:
                raise DataIntegrityError(f"Could not download {url}: {error}") from error
            time.sleep(2 * attempt)


def validate_schema(path: Path, name: str, expected: list[str]) -> None:
    """Fail with a useful message if CDC changed the columns this pipeline depends on."""
    _, meta = pyreadstat.read_xport(str(path), metadataonly=True)
    present = {column.upper() for column in meta.column_names}
    missing = [column for column in expected if column.upper() not in present]
    if missing:
        raise DataIntegrityError(
            f"{name}: expected columns {missing} are missing. CDC may have revised this file. "
            f"Columns found: {sorted(present)}. Update configs/analysis.yml and docs/data_dictionary.md."
        )


def load_manifest(config: Config) -> dict[str, Any]:
    if config.manifest_path.exists():
        return json.loads(config.manifest_path.read_text(encoding="utf-8"))
    return {"schema_version": 1, "files": {}}


def download(config: Config, refresh_manifest: bool = False, force: bool = False) -> dict[str, Any]:
    """Fetch every file, check its schema, and verify or record its SHA-256.

    With an existing manifest, a hash mismatch is an error unless ``refresh_manifest`` is set.
    """
    manifest = load_manifest(config)
    files: dict[str, Any] = dict(manifest.get("files", {}))
    for name, columns in config.files.items():
        path = local_path(config, name)
        if force or not path.exists():
            _fetch(source_url(config, name), path)
            retrieved = datetime.now(UTC).date().isoformat()
        else:
            retrieved = files.get(name, {}).get("retrieved_at", datetime.now(UTC).date().isoformat())
        validate_schema(path, name, columns)
        digest = _sha256(path)
        recorded = files.get(name)
        if recorded and recorded["sha256"] != digest and not refresh_manifest:
            raise DataIntegrityError(
                f"{name}: SHA-256 {digest[:12]}... does not match the manifest "
                f"{recorded['sha256'][:12]}.... CDC may have revised the file. Rerun with "
                "--refresh-manifest to accept the new file and review the change."
            )
        files[name] = {
            "source_url": source_url(config, name),
            "retrieved_at": retrieved if not recorded or recorded["sha256"] != digest else recorded["retrieved_at"],
            "bytes": path.stat().st_size,
            "sha256": digest,
            "columns_verified": columns,
        }
    manifest = {"schema_version": 1, "files": files}
    config.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    config.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
