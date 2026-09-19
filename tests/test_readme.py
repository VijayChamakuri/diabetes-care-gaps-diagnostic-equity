"""The real README: numbers live only in generated blocks, and the blocks match outputs/tables."""

import re
from pathlib import Path

import pytest

from nhanes_diabetes.config import load_config
from nhanes_diabetes.report import BLOCKS, MARK, check_readme

REPO = Path(__file__).resolve().parents[1]
README = (REPO / "README.md").read_text(encoding="utf-8")


def _outside_blocks() -> str:
    return MARK.sub("", README)


def test_every_generated_block_is_present() -> None:
    found = {m.group("name") for m in MARK.finditer(README)}
    assert set(BLOCKS) <= found


def test_no_statistics_are_hard_coded_outside_generated_blocks() -> None:
    prose = re.sub(r"```.*?```", "", _outside_blocks(), flags=re.S)
    prose = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", prose)  # images and badges, including alt text and URL-encoded targets
    prose = re.sub(r"\]\([^)]*\)", "]", prose)  # link targets
    prose = prose.replace("6.5%", "").replace("95%", "")  # the criterion and the interval level are definitions
    assert re.findall(r"\d+(?:\.\d+)?\s?%", prose) == []
    assert re.findall(r"\bp\s?[<=]\s?0?\.\d+", prose) == []
    assert re.findall(r"\bAUC\b[^.\n]*\d\.\d{2,}", prose) == []


@pytest.mark.skipif(not (REPO / "outputs/tables/undiagnosis_estimates.csv").exists(), reason="outputs not generated")
def test_generated_blocks_match_the_committed_tables() -> None:
    assert check_readme(load_config(root=REPO)) == []
