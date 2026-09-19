"""The stakeholder brief, the Tableau package and the claims the documents may make."""

import re
from pathlib import Path

import pandas as pd
import pytest

from nhanes_diabetes import brief
from nhanes_diabetes.config import load_config
from nhanes_diabetes.tableau import check_tableau, render_tableau

REPO = Path(__file__).resolve().parents[1]
TABLES = REPO / "outputs" / "tables"
needs_outputs = pytest.mark.skipif(not (TABLES / "undiagnosis_estimates.csv").exists(), reason="outputs not generated")

DOCS = [REPO / "README.md", REPO / "excel" / "README.md", REPO / "reports" / "healthcare_quality_brief.md",
        REPO / "CONTRIBUTING.md", *sorted((REPO / "docs").glob("*.md")), *sorted((REPO / "tableau").glob("*.md"))]
NEGATION = re.compile(r"\b(not|no|never|without|cannot|nor|neither|nothing|none|until|unless|mistaken)\b|n't", re.I)
GUARDED = ["HEDIS", "Epic", "Clarity", "Caboodle", "HIPAA", "Tableau dashboard", "real patient", "savings"]


@needs_outputs
def test_committed_brief_matches_the_tables() -> None:
    assert brief.check_brief(load_config(root=REPO)) == []


@needs_outputs
def test_brief_has_the_required_sections_in_order() -> None:
    text = (REPO / brief.BRIEF).read_text(encoding="utf-8")
    headings = [h for h in re.findall(r"^## (.+)$", text, flags=re.M)]
    assert headings[:6] == ["Decision question", "Population and exclusions", "Three computed findings, with uncertainty",
                            "What this means for screening outreach", "What the data cannot establish",
                            "Recommended next analysis"]
    assert "Metric glossary" in headings
    assert len(re.findall(r"^\d\. \*\*", text.split("## Three computed findings")[1].split("## What this means")[0], flags=re.M)) == 3


def test_fixed_brief_prose_contains_no_statistics() -> None:
    fixed = [brief.INTRO, brief.DECISION_QUESTION, *brief.CANNOT_ESTABLISH, *brief.NEXT_ANALYSIS]
    for text in fixed:
        assert not re.search(r"\d", text.replace("HbA1c", "")), text


@needs_outputs
def test_brief_never_calls_the_analysis_a_certified_measure() -> None:
    text = (REPO / brief.BRIEF).read_text(encoding="utf-8")
    assert "care-gap monitoring" in text and "measure-inspired" in text
    for line in text.splitlines():
        if "HEDIS" in line:
            assert re.search(r"\bnot a certified HEDIS\b", line), line


@needs_outputs
def test_brief_uses_the_generated_numbers() -> None:
    text = (REPO / brief.BRIEF).read_text(encoding="utf-8")
    est = pd.read_csv(TABLES / "undiagnosis_estimates.csv").set_index("group")
    assert f"{est.loc['All groups', 'estimate'] * 100:.1f}%" in text
    assert f"{int(est.loc['All groups', 'respondents']):,} respondents" in text


@needs_outputs
def test_tableau_extracts_match_the_tables() -> None:
    assert check_tableau(load_config(root=REPO)) == []


@needs_outputs
def test_tableau_extracts_are_aggregates_only() -> None:
    forbidden = {"seqn", "weight", "psu", "stratum", "age", "hba1c", "respondent_id"}
    for name in ("care_gap_summary", "model_tradeoffs", "cohort_flow"):
        frame = pd.read_csv(REPO / "tableau" / "data" / f"{name}.csv")
        assert not (forbidden & {c.lower() for c in frame.columns}), name
        assert len(frame) < 400
    care = pd.read_csv(REPO / "tableau" / "data" / "care_gap_summary.csv").set_index("group")
    est = pd.read_csv(TABLES / "undiagnosis_estimates.csv").set_index("group")
    assert care.loc["All groups", "undiagnosed_share"] == pytest.approx(est.loc["All groups", "estimate"], abs=1e-9)
    assert care["is_all_groups"].sum() == 1


@needs_outputs
def test_tableau_field_dictionary_covers_every_column() -> None:
    files = render_tableau(load_config(root=REPO))
    dictionary = files["field_dictionary.md"]
    for rel, text in files.items():
        if rel.endswith(".csv"):
            for column in text.splitlines()[0].split(","):
                assert f"`{column}`" in dictionary, (rel, column)
    assert not re.search(r"\|  \|$", dictionary, flags=re.M), "a field has no description"


def test_no_tableau_workbook_and_no_placeholder_url_exist() -> None:
    files = [p for p in REPO.rglob("*") if ".venv" not in p.parts and ".git" not in p.parts]
    assert not [p for p in files if p.suffix.lower() in {".twb", ".twbx", ".hyper", ".tds", ".tdsx"}]
    readme = (REPO / "tableau" / "README.md").read_text(encoding="utf-8")
    assert "no Tableau workbook has been built or published" in readme
    assert "public.tableau.com" not in readme
    for doc in DOCS:
        assert "public.tableau.com" not in doc.read_text(encoding="utf-8"), doc


def test_readme_labels_html_versus_tableau() -> None:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "A Tableau or Power BI version is not included" not in text
    assert "no Tableau or Power BI workbook" in text and "HTML dashboard" in text


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(REPO)))
def test_guarded_terms_only_appear_in_denials(doc: Path) -> None:
    for number, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), start=1):
        for term in GUARDED:
            if term.lower() in line.lower():
                assert NEGATION.search(line), f"{doc.relative_to(REPO)}:{number} uses '{term}' without a denial: {line}"


def test_documents_have_no_em_dashes() -> None:
    for doc in DOCS:
        assert chr(0x2014) not in doc.read_text(encoding="utf-8"), doc
