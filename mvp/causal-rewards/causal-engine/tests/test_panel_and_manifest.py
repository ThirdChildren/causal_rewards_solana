"""Panel guardrails (missingness, washout, min-sample) and manifest semantic checks."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from crp_engine.manifest import Manifest, ManifestError, parse_weight_formula
from crp_engine.panel import IdentificationMode, load_panel


def _frame(n_cohorts=4, n_blocks=8, *, outcome=1.0) -> pd.DataFrame:
    rows = []
    for c in range(n_cohorts):
        for t in range(n_blocks):
            rows.append(
                {
                    "cohort_id": "geo%d" % c,
                    "time_block": t,
                    "arm": "treatment" if (t + c) % 2 else "control",
                    "outcome": outcome + 0.01 * t,
                    "n_units": 10,
                    "n_observations": 100,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def m_small(manifest_obj) -> Manifest:
    manifest_obj["analysis_plan"]["minimum_sample"] = {
        "min_units_per_cohort": "5",
        "min_observations_per_cohort": "200",
        "min_time_blocks": "4",
        "min_eligible_cohorts": "2",
    }
    manifest_obj["analysis_plan"]["covariate_adjustment"] = []
    manifest_obj["analysis_plan"]["sensitivity_analyses"] = []
    return Manifest.from_obj(manifest_obj)


# ------------------------------------------------------------------ missingness

def test_missing_outcomes_are_excluded_and_counted(m_small) -> None:
    f = _frame()
    f.loc[[0, 5, 9], "outcome"] = np.nan
    panel = load_panel(f, m_small)
    assert panel.excluded["missing_data_ineligible"] == 3
    assert len(panel.frame) == len(f) - 3


def test_imputation_policy_is_honoured_when_frozen(manifest_obj) -> None:
    manifest_obj["design"]["parameters"]["missingness_policy"] = "impute_cohort_mean"
    manifest_obj["analysis_plan"]["minimum_sample"]["min_time_blocks"] = "4"
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "2"
    manifest_obj["analysis_plan"]["covariate_adjustment"] = []
    m = Manifest.from_obj(manifest_obj)
    f = _frame()
    f.loc[[0, 5], "outcome"] = np.nan
    panel = load_panel(f, m)
    assert panel.excluded["missing_data_imputed"] == 2
    assert len(panel.frame) == len(f)
    assert not panel.frame["outcome"].isna().any()


def test_unknown_missingness_policy_is_rejected(manifest_obj) -> None:
    manifest_obj["design"]["parameters"]["missingness_policy"] = "drop_worst_half"
    with pytest.raises(ManifestError, match="missingness_policy"):
        Manifest.from_obj(manifest_obj)


# ------------------------------------------------------------------ washout

def test_switchback_washout_discards_post_switch_blocks(manifest_obj) -> None:
    manifest_obj["design"]["template"] = "switchback"
    manifest_obj["design"]["parameters"]["carryover_blocks"] = "1"
    manifest_obj["design"]["parameters"]["washout_blocks"] = "1"
    manifest_obj["treatment"]["assignment_method"] = "switchback_schedule"
    manifest_obj["treatment"]["treated_fraction_micro"] = "500000"
    manifest_obj["analysis_plan"]["estimator"] = "switchback_hac"
    manifest_obj["analysis_plan"]["standard_error_method"] = "hac"
    manifest_obj["analysis_plan"]["covariate_adjustment"] = []
    manifest_obj["analysis_plan"]["sensitivity_analyses"] = []
    manifest_obj["analysis_plan"]["minimum_sample"]["min_time_blocks"] = "2"
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "2"
    m = Manifest.from_obj(manifest_obj)

    # Two periods of 4 blocks each: arm flips at block 4.
    rows = []
    for c in range(4):
        for t in range(8):
            rows.append(
                {
                    "cohort_id": "geo%d|%d" % (c, t // 4),
                    "time_block": t,
                    "arm": "treatment" if t < 4 else "control",
                    "outcome": 1.0,
                    "n_units": 10,
                    "n_observations": 100,
                }
            )
    panel = load_panel(pd.DataFrame(rows), m)
    # The flip happens at block 4 within each GEO; block 4 is discarded, block 0 is not
    # (nothing precedes the start of the experiment).
    assert panel.excluded["switchback_washout"] == 4
    assert set(panel.frame["time_block"]) == {0, 1, 2, 3, 5, 6, 7}


def test_switchback_requires_half_treated_fraction(manifest_obj) -> None:
    manifest_obj["design"]["template"] = "switchback"
    manifest_obj["design"]["parameters"]["carryover_blocks"] = "1"
    manifest_obj["design"]["parameters"]["washout_blocks"] = "1"
    manifest_obj["treatment"]["treated_fraction_micro"] = "250000"
    with pytest.raises(ManifestError, match="500000"):
        Manifest.from_obj(manifest_obj)


def test_washout_must_be_at_least_carryover(manifest_obj) -> None:
    manifest_obj["design"]["template"] = "switchback"
    manifest_obj["design"]["parameters"]["carryover_blocks"] = "3"
    manifest_obj["design"]["parameters"]["washout_blocks"] = "1"
    with pytest.raises(ManifestError, match="washout_blocks"):
        Manifest.from_obj(manifest_obj)


# ------------------------------------------------------------------ minimum sample

def test_minimum_sample_flags_are_per_threshold(m_small) -> None:
    f = _frame()
    f.loc[f["cohort_id"] == "geo0", "n_units"] = 1          # below min_units
    f.loc[f["cohort_id"] == "geo1", "n_observations"] = 1   # below min_observations
    f = f[~((f["cohort_id"] == "geo2") & (f["time_block"] >= 2))]  # below min_time_blocks
    panel = load_panel(f, m_small)
    assert "below_min_units_per_cohort" in panel.samples["geo0"].reasons
    assert "below_min_observations_per_cohort" in panel.samples["geo1"].reasons
    assert "below_min_time_blocks" in panel.samples["geo2"].reasons
    assert panel.samples["geo3"].eligible


# ------------------------------------------------------------------ panel validation

def test_duplicate_cohort_block_rows_are_rejected(m_small) -> None:
    f = pd.concat([_frame(), _frame().head(1)])
    with pytest.raises(ValueError, match="duplicate"):
        load_panel(f, m_small)


def test_invalid_arm_label_is_rejected(m_small) -> None:
    f = _frame()
    f.loc[0, "arm"] = "maybe"
    with pytest.raises(ValueError, match="arm"):
        load_panel(f, m_small)


def test_missing_required_column_is_rejected(m_small) -> None:
    f = _frame().drop(columns=["n_observations"])
    with pytest.raises(ValueError, match="missing required columns"):
        load_panel(f, m_small)


def test_upstream_eligibility_flag_is_honoured_and_counted(m_small) -> None:
    f = _frame()
    f["eligible"] = True
    f.loc[[1, 2, 3], "eligible"] = False
    panel = load_panel(f, m_small)
    assert panel.excluded["upstream_ineligible"] == 3


def test_panel_row_order_does_not_change_the_result(m_small) -> None:
    f = _frame()
    a = load_panel(f, m_small)
    b = load_panel(f.sample(frac=1.0, random_state=3), m_small)
    pd.testing.assert_frame_equal(a.frame, b.frame)
    assert a.identification is b.identification


# ------------------------------------------------------------------ manifest guards

def test_unit_type_must_be_cohort_time_block(manifest_obj) -> None:
    manifest_obj["estimand"]["unit_type"] = "device"
    with pytest.raises(ManifestError, match="Invariant 4"):
        Manifest.from_obj(manifest_obj)


def test_reward_curve_hash_is_verified(manifest_obj) -> None:
    manifest_obj["reward_policy"]["reward_curve"]["breakpoints"][1][1] = "20000000001"
    with pytest.raises(ManifestError, match="reward_curve_hash mismatch"):
        Manifest.from_obj(manifest_obj)


def test_reward_curve_must_start_at_origin(manifest_obj) -> None:
    manifest_obj["reward_policy"]["reward_curve"]["breakpoints"][0] = ["1", "0"]
    with pytest.raises(ManifestError, match="first breakpoint|reward_curve_hash"):
        Manifest.from_obj(manifest_obj)


def test_test_sidedness_must_be_one_sided_lower(manifest_obj) -> None:
    manifest_obj["analysis_plan"]["test_sidedness"] = "two_sided"
    with pytest.raises(ManifestError, match="Invariant 3"):
        Manifest.from_obj(manifest_obj)


def test_student_t_requires_df(manifest_obj) -> None:
    manifest_obj["analysis_plan"]["critical_value_reference"] = "student_t"
    with pytest.raises(ManifestError, match="requires df"):
        Manifest.from_obj(manifest_obj)


def test_normal_approx_must_not_carry_df(manifest_obj) -> None:
    manifest_obj["analysis_plan"]["df"] = "42"
    with pytest.raises(ManifestError, match="must not carry df"):
        Manifest.from_obj(manifest_obj)


def test_parse_weight_formula_accepts_the_frozen_grammar() -> None:
    assert parse_weight_formula("1*quality_adjusted_observations") == [
        (1, "quality_adjusted_observations")
    ]
    assert parse_weight_formula("1000000*uptime_micro + 2*accepted_observations") == [
        (1000000, "uptime_micro"),
        (2, "accepted_observations"),
    ]


@pytest.mark.parametrize(
    "bad",
    ["1 * uptime_micro", "1*uptime_micro+2*accepted_observations", "uptime_micro",
     "1*uptime_micro - 2*accepted_observations", "01*uptime_micro", ""],
)
def test_parse_weight_formula_rejects_malformed_input(bad: str) -> None:
    with pytest.raises(ManifestError):
        parse_weight_formula(bad)
