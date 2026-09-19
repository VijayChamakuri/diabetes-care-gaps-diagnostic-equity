"""End to end on a synthetic fixture: the same code path as real data, no network."""

import json
import re
import shutil

import pandas as pd
import pyreadstat
import pytest

from nhanes_diabetes import analysis, dashboard, report
from nhanes_diabetes.crosscheck import compare, python_estimates, r_survey_available, run_crosscheck
from nhanes_diabetes.download import download
from nhanes_diabetes.plots import make_figures
from tests.fixtures import REPO, make_config, synthetic_raw


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    root = tmp_path_factory.mktemp("proj")
    config = make_config(root)
    (root / "dashboard").mkdir()
    for name in ("template.html", "style.css", "app.js"):
        (root / "dashboard" / name).write_text((REPO / "dashboard" / name).read_text())
    shutil.copytree(REPO / "r", root / "r")
    (root / "configs").mkdir()
    shutil.copy(REPO / "configs" / "analysis.yml", root / "configs" / "analysis.yml")
    config.raw_dir.mkdir(parents=True)
    for name, frame in synthetic_raw(3000, seed=11).items():
        pyreadstat.write_xport(frame, str(config.raw_dir / f"{name}.xpt"), file_format_version=5)
    download(config)  # files exist, so this only verifies schema and records hashes
    analysis.build(config)
    tables = analysis.analyze(config)
    analysis.write_manifest(config)
    return config, tables


def test_pipeline_writes_every_named_table(project) -> None:
    config, tables = project
    expected = {"undiagnosis_estimates", "undiagnosis_contrasts", "weighted_prevalence", "baseline_characteristics",
                "missingness_by_group", "age_standardized_undiagnosis", "robustness", "model_specification",
                "feature_specification", "subgroup_metrics", "specificity_cost", "sensitivity_gap", "auc",
                "auc_difference", "brier_by_group", "calibration", "thresholds"}
    assert expected <= set(tables)
    on_disk = {p.stem for p in config.tables_dir.glob("*.csv")}
    assert expected | {"cohort_attrition", "data_quality", "group_summary"} <= on_disk


def test_estimates_are_internally_consistent(project) -> None:
    _, tables = project
    est = tables["undiagnosis_estimates"].set_index("group")
    assert est.loc["All groups", "respondents"] == est.drop("All groups")["respondents"].sum()
    assert ((est["estimate"] >= 0) & (est["estimate"] <= 1)).all()
    con = tables["undiagnosis_contrasts"]
    assert (con["p_value_holm"] >= con["p_value"] - 1e-12).all()
    assert con["analysis_type"].eq("confirmatory").sum() == 1
    sub = tables["subgroup_metrics"]
    assert sub[["sensitivity", "specificity"]].dropna().ge(0).all().all()
    diff = tables["auc_difference"]
    assert (diff["ci_low"] <= diff["difference"] + 1e-9).all() or diff["ci_low"].isna().any()


def test_run_manifest_records_provenance(project) -> None:
    config, tables = project
    manifest = json.loads((config.root / "outputs" / "run_manifest.json").read_text())
    assert manifest["seed"] == config.analysis("seed")
    assert set(manifest["source_files"]) == set(config.files)
    assert manifest["sample_counts"]["analysis_cohort"] == int(pd.read_csv(config.tables_dir / "cohort_attrition.csv")["n"].iloc[-1])
    assert "undiagnosis_estimates.csv" in manifest["outputs"] and manifest["packages"]["numpy"]


def test_analysis_is_reproducible(project) -> None:
    config, tables = project
    again = analysis.analyze(config)
    pd.testing.assert_frame_equal(tables["undiagnosis_estimates"], again["undiagnosis_estimates"])
    pd.testing.assert_frame_equal(tables["subgroup_metrics"], again["subgroup_metrics"])
    pd.testing.assert_frame_equal(tables["auc_difference"], again["auc_difference"])


def test_readme_blocks_are_generated_and_drift_is_detected(project) -> None:
    config, _ = project
    template = "\n".join(f"## {n}\n<!-- BEGIN generated:{n} -->\nold\n<!-- END generated:{n} -->\n" for n in report.BLOCKS)
    (config.root / "README.md").write_text(template)
    assert len(report.check_readme(config)) == len(report.BLOCKS)  # stale placeholder text is caught
    report.write_readme(config)
    assert report.check_readme(config) == []
    path = config.tables_dir / "undiagnosis_estimates.csv"
    frame = pd.read_csv(path)
    frame.loc[frame["group"] == "All groups", "estimate"] += 0.05
    frame.to_csv(path, index=False)
    assert "block 'headline' does not match outputs/tables" in report.check_readme(config)


def test_figures_and_dashboard_build(project) -> None:
    config, tables = project
    analysis.write_tables(config.tables_dir, tables)  # restore tables edited by the drift test
    make_figures(config)
    for name in ("undiagnosis_by_group", "sensitivity_by_group", "specificity_cost", "calibration"):
        for ext in ("png", "svg"):
            assert (config.figures_dir / f"{name}.{ext}").stat().st_size > 1000
    assert "Figure alt text" in (config.figures_dir / "ALT_TEXT.md").read_text()
    html = dashboard.build_dashboard(config).read_text()
    assert "/*DATA*/" not in html and html.count("<script") == 2
    payload = dashboard.build_payload(config)
    est = tables["undiagnosis_estimates"]
    assert payload["undiagnosis"][0]["estimate"] == pytest.approx(est.loc[0, "estimate"])
    assert re.search(r"https?://", html) is None


@pytest.mark.skipif(not r_survey_available(), reason="R with the survey package is not installed")
def test_python_matches_r_survey_on_the_fixture(project) -> None:
    config, _ = project
    result = run_crosscheck(config)
    assert result is not None and (result["status"] == "pass").all()


def test_crosscheck_flags_a_mismatch(project) -> None:
    config, _ = project
    cohort = pd.read_csv(config.processed_dir / "cohort.csv")
    py = python_estimates(cohort, config)
    r = py.copy()
    assert (compare(py, r)["status"] == "pass").all()
    r.loc[0, "se"] += 1e-3
    bad = compare(py, r)
    assert (bad["status"] == "FAIL").sum() == 1 and bad.loc[bad["status"] == "FAIL", "quantity"].iloc[0] == "se"


def test_cli_stages_run_and_report_check_fails_on_drift(project, capsys) -> None:
    from nhanes_diabetes.cli import main

    config, tables = project
    analysis.write_tables(config.tables_dir, tables)
    template = "\n".join(f"<!-- BEGIN generated:{n} -->\n<!-- END generated:{n} -->" for n in report.BLOCKS)
    (config.root / "README.md").write_text(template)
    root = ["--root", str(config.root)]
    assert main([*root, "report"]) == 0
    assert main([*root, "report", "--check"]) == 0
    assert main([*root, "dashboard"]) == 0
    assert main([*root, "build-cohort"]) == 0
    assert "data-quality checks passed" in capsys.readouterr().out
    (config.root / "README.md").write_text(template)  # blocks emptied: now out of sync
    with pytest.raises(SystemExit):
        main([*root, "report", "--check"])
    with pytest.raises(SystemExit):
        main([*root, "no-such-command"])
