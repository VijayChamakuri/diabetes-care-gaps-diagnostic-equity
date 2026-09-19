import duckdb
import pandas as pd
import pytest

from nhanes_diabetes.cohort import CohortError, Variant, build_cohort
from tests.fixtures import load_synthetic, make_config, synthetic_raw


@pytest.fixture()
def config(tmp_path):
    return make_config(tmp_path)


def _build(config, frames=None, variant=None):
    con = duckdb.connect(":memory:")
    load_synthetic(con, frames)
    return con, build_cohort(con, config, variant)


def test_attrition_is_monotone_and_ends_at_the_cohort(config) -> None:
    _, cohort = _build(config)
    n = cohort.attrition["n"].tolist()
    assert n == sorted(n, reverse=True)
    assert n[-1] == len(cohort.data)
    assert cohort.attrition["removed"].tolist()[0] == 0
    assert cohort.quality["passed"].all()


def test_rules_exclude_the_right_people(config) -> None:
    frames = synthetic_raw()
    _, cohort = _build(config, frames)
    demo = frames["DEMO_J"].set_index("SEQN")
    diq = frames["DIQ_J"].set_index("SEQN")["DIQ010"]
    ghb = frames["GHB_J"].set_index("SEQN")["LBXGH"]
    kept = set(cohort.data["seqn"])
    assert all(demo.loc[s, "WTMEC2YR"] > 0 for s in kept)  # exam weight required
    assert all(diq.loc[s] in (1.0, 2.0) for s in kept)  # borderline and don't-know excluded
    assert all(pd.notna(ghb.loc[s]) for s in kept)  # HbA1c required
    nine = diq[diq == 9.0].index
    assert not kept & set(nine)  # code 9 is missing, never "not diagnosed"


def test_missing_codes_become_null_not_no(config) -> None:
    frames = synthetic_raw()
    con, cohort = _build(config, frames)
    assert cohort.data["insured"].isin([0, 1]).sum() + cohort.data["insured"].isna().sum() == len(cohort.data)
    seq_seven = set(frames["HIQ_J"].loc[frames["HIQ_J"]["HIQ011"] == 7.0, "SEQN"]) & set(cohort.data["seqn"])
    assert seq_seven
    assert cohort.data[cohort.data["seqn"].isin(seq_seven)]["insured"].isna().all()


def test_variants_change_only_what_they_claim(config) -> None:
    frames = synthetic_raw()
    _, main = _build(config, frames)
    _, pos = _build(config, frames, Variant("p", "positive"))
    _, neg = _build(config, frames, Variant("n", "negative"))
    _, adults = _build(config, frames, Variant("a", "exclude", 18))
    assert len(pos.data) == len(neg.data) > len(main.data)
    assert len(adults.data) < len(main.data) and adults.data["age"].min() >= 18
    border = set(pos.data["seqn"]) - set(main.data["seqn"])
    assert border and pos.data[pos.data["seqn"].isin(border)]["diagnosed"].eq(1).all()
    assert neg.data[neg.data["seqn"].isin(border)]["diagnosed"].eq(0).all()


def test_duplicate_respondents_stop_the_pipeline(config) -> None:
    frames = synthetic_raw()
    frames["DEMO_J"] = pd.concat([frames["DEMO_J"], frames["DEMO_J"].head(3)], ignore_index=True)
    with pytest.raises(CohortError, match="seqn_unique|independent_recount"):
        _build(config, frames)


def test_bad_design_variables_stop_the_pipeline(config) -> None:
    frames = synthetic_raw()
    frames["DEMO_J"].loc[0:40, "SDMVPSU"] = 7.0
    frames["DEMO_J"].loc[frames["DEMO_J"]["WTMEC2YR"] > 0, "WTMEC2YR"] = frames["DEMO_J"]["WTMEC2YR"]
    with pytest.raises(CohortError, match="psu_masked_values"):
        _build(config, frames)


def test_implausible_hba1c_stops_the_pipeline(config) -> None:
    frames = synthetic_raw()
    frames["GHB_J"].loc[frames["GHB_J"]["LBXGH"].notna().idxmax(), "LBXGH"] = 55.0
    with pytest.raises(CohortError, match="hba1c_present_and_plausible"):
        _build(config, frames)
