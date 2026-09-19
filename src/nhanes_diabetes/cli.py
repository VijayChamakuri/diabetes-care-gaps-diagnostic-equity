"""Command line interface: ``python -m nhanes_diabetes <command>``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from nhanes_diabetes.config import Config, load_config


def _download(config: Config, args: argparse.Namespace) -> None:
    from nhanes_diabetes.download import download

    manifest = download(config, refresh_manifest=args.refresh_manifest, force=args.force)
    print(f"Verified {len(manifest['files'])} files; manifest at {config.manifest_path}")


def _build_cohort(config: Config, args: argparse.Namespace) -> None:
    from nhanes_diabetes.analysis import build

    cohort = build(config)
    print(cohort.attrition.to_string(index=False))
    print(f"\n{int(cohort.quality['passed'].sum())}/{len(cohort.quality)} data-quality checks passed")


def _analyze(config: Config, args: argparse.Namespace) -> None:
    from nhanes_diabetes.analysis import analyze, write_manifest

    tables = analyze(config)
    write_manifest(config)
    print(f"Wrote {len(tables)} tables to {config.tables_dir}")


def _crosscheck(config: Config, args: argparse.Namespace) -> None:
    from nhanes_diabetes.crosscheck import run_crosscheck

    result = run_crosscheck(config, require_r=not args.skip_if_no_r)
    if result is None:
        print("R survey package not available; cross-check skipped")
        return
    failed = int((result["status"] != "pass").sum())
    print(f"{len(result) - failed}/{len(result)} Python estimates match R survey")
    if failed:
        raise SystemExit(1)


def _report(config: Config, args: argparse.Namespace) -> None:
    from nhanes_diabetes.brief import check_brief, write_brief
    from nhanes_diabetes.plots import make_figures
    from nhanes_diabetes.report import check_readme, write_readme
    from nhanes_diabetes.tableau import check_tableau, write_tableau
    from nhanes_diabetes.workbook import verify_workbook

    make_figures(config)
    if args.check:
        problems = check_readme(config) + check_brief(config) + check_tableau(config) + verify_workbook(config)
        if problems:
            print("Generated artifacts are out of sync with outputs/tables:\n  " + "\n  ".join(problems))
            raise SystemExit(1)
        print("README, brief, Tableau extracts and workbook match outputs/tables")
    else:
        write_readme(config)
        write_brief(config)
        write_tableau(config)
        print("Figures written; README blocks, stakeholder brief and Tableau extracts refreshed")


def _excel(config: Config, args: argparse.Namespace) -> None:
    from nhanes_diabetes.workbook import build_workbook

    print(build_workbook(config))


def _dashboard(config: Config, args: argparse.Namespace) -> None:
    from nhanes_diabetes.dashboard import build_dashboard

    print(build_dashboard(config))


def _all(config: Config, args: argparse.Namespace) -> None:
    _download(config, argparse.Namespace(refresh_manifest=False, force=False))
    _build_cohort(config, args)
    _analyze(config, args)
    _crosscheck(config, argparse.Namespace(skip_if_no_r=True))
    _report(config, argparse.Namespace(check=False))
    _excel(config, args)
    _dashboard(config, args)


COMMANDS: dict[str, tuple[str, Callable[[Config, argparse.Namespace], None]]] = {
    "download": ("Download NHANES files, verify schema and hashes", _download),
    "build-cohort": ("Load DuckDB, run the cohort and data-quality SQL", _build_cohort),
    "analyze": ("Run estimates, models and robustness; write outputs/tables", _analyze),
    "crosscheck": ("Compare Python survey estimates with R's survey package", _crosscheck),
    "report": ("Regenerate figures, README blocks, the stakeholder brief and Tableau extracts", _report),
    "excel": ("Build the seven-sheet Excel quality review from outputs/tables", _excel),
    "dashboard": ("Build the offline dashboard from outputs/tables", _dashboard),
    "all": ("Run every stage in order", _all),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nhanes-diabetes", description=__doc__)
    parser.add_argument("--config", type=Path, default=None, help="Path to analysis.yml")
    parser.add_argument("--root", type=Path, default=None, help="Project root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (help_text, _) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        if name == "download":
            p.add_argument("--refresh-manifest", action="store_true",
                           help="Accept changed CDC files and rewrite the manifest")
            p.add_argument("--force", action="store_true", help="Download again even if the file exists")
        if name == "crosscheck":
            p.add_argument("--skip-if-no-r", action="store_true", help="Skip quietly when R is unavailable")
        if name == "report":
            p.add_argument("--check", action="store_true", help="Fail if the README, brief, Tableau extracts or workbook do not match outputs")
    args = parser.parse_args(argv)
    config = load_config(args.config, args.root)
    COMMANDS[args.command][1](config, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
