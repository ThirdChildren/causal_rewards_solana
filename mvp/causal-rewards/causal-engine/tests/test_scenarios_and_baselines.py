"""Integration over the simulator's benchmark scenarios + the four-baseline comparison.

These tests assert the HONEST properties of the pipeline, not that "causal wins":

* a true-null scenario must not produce broad positive payouts,
* an underpowered scenario must be allowed to return the whole budget,
* observational replay must pay nothing,
* every allocator must respect the same fixed budget.

They are skipped when the simulator outputs have not been generated
(``cd simulator && make baseline`` / ``python -m depin_sim.cli run --scenario ...``).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from crp_engine.adapters import panel_from_simulator, participants_from_simulator
from crp_engine.baselines import BASELINES, CohortFeatures, allocate_baseline
from crp_engine.manifest import Manifest
from crp_engine.panel import IdentificationMode
from crp_engine.run import analyze
from tests.conftest import REPO, SPEC_MANIFEST

SIM_OUT = REPO / "simulator" / "out"
SEED = bytes.fromhex("00" * 24 + "0123456789abcdef")


def _manifest(name: str, panel: pd.DataFrame, *, replay: bool = False) -> Manifest:
    obj = copy.deepcopy(json.loads(SPEC_MANIFEST.read_text(encoding="utf-8")))
    obj["experiment_id"] = "bench-" + name
    obj["analysis_plan"]["covariate_adjustment"] = []
    obj["analysis_plan"]["sensitivity_analyses"] = []
    obj["analysis_plan"]["minimum_sample"] = {
        "min_units_per_cohort": "3",
        "min_observations_per_cohort": "200",
        "min_time_blocks": "6",
        "min_eligible_cohorts": "10",
    }
    obj["estimand"]["cohort_definition"]["cohort_count"] = str(panel["cohort_id"].nunique())
    obj["estimand"]["time_block"]["block_count"] = str(panel["time_block"].nunique())
    if replay:
        obj["design"]["template"] = "observational_replay"
        obj["design"]["eligible_for_strong_causal_claim"] = False
    return Manifest.from_obj(obj)


def _load(scenario: str):
    d = SIM_OUT / scenario
    if not (d / "cohort_blocks.parquet").is_file():
        pytest.skip("simulator output for %s not generated" % scenario)
    cb = pd.read_parquet(d / "cohort_blocks.parquet")
    sensors = pd.read_parquet(d / "sensors.parquet")
    return panel_from_simulator(cb), participants_from_simulator(sensors, cb), cb


def test_adapter_maps_the_simulator_table_onto_the_panel_contract() -> None:
    panel, parts, _ = _load("s1_strong_signal")
    from crp_engine.panel import REQUIRED_COLUMNS

    assert set(REQUIRED_COLUMNS) <= set(panel.columns)
    assert set(panel["arm"]) <= {"treatment", "control"}
    assert set(parts.columns) == {
        "cohort_id", "recipient_hex", "accepted_observations",
        "quality_adjusted_observations",
    }
    assert all(len(h) == 64 for h in parts["recipient_hex"])


def test_whole_cohort_scenarios_are_flagged_as_control_pool_identification() -> None:
    """The simulator randomizes WHOLE cohorts, so no within-cohort contrast exists. Say so."""
    panel, parts, _ = _load("s1_strong_signal")
    run = analyze(_manifest("s1", panel), panel, parts, seed=SEED)
    assert run.panel.identification is IdentificationMode.BETWEEN_COHORT_VS_CONTROL_POOL
    assert not json.dumps(run.analysis["identification"]).count("within_cohort")
    assert run.analysis["identification"]["supports_strong_causal_claim"] == "false"


def test_null_scenario_leaves_most_cohorts_at_zero() -> None:
    panel, parts, _ = _load("s2_null_effect")
    run = analyze(_manifest("s2", panel), panel, parts, seed=SEED)
    s1 = run.compilation.stage1
    positive = [c for c in s1.cohorts if c.conservative_s > 0]
    assert len(positive) < 0.15 * len(s1.cohorts), (
        "a true-null scenario paid %d of %d cohorts" % (len(positive), len(s1.cohorts))
    )


def test_low_power_scenario_may_return_the_whole_budget() -> None:
    panel, parts, _ = _load("s3_low_power")
    run = analyze(_manifest("s3", panel), panel, parts, seed=SEED)
    s1 = run.compilation.stage1
    assert run.compilation.total_leaf_base_units <= s1.budget_base_units
    if s1.null_distribution:
        assert run.compilation.reward_root_hex == "00" * 32
        assert run.compilation.total_leaf_base_units == 0


def test_observational_replay_pays_nothing_end_to_end() -> None:
    panel, parts, _ = _load("s6_demand_shift")
    run = analyze(_manifest("s6", panel, replay=True), panel, parts, seed=SEED)
    assert run.compilation.total_leaf_base_units == 0
    assert run.compilation.reward_root_hex == "00" * 32
    assert run.analysis["reward_summary"]["null_distribution"] == "true"


@pytest.mark.parametrize(
    "scenario",
    ["s1_strong_signal", "s2_null_effect", "s4_interference", "s5_sybil_contamination"],
)
def test_budget_is_never_exceeded_in_any_scenario(scenario: str) -> None:
    panel, parts, _ = _load(scenario)
    m = _manifest(scenario, panel)
    run = analyze(m, panel, parts, seed=SEED)
    assert run.compilation.total_leaf_base_units <= m.reward_policy.budget_base_units


# ------------------------------------------------------------------ four baselines

def test_all_four_baselines_respect_the_same_fixed_budget() -> None:
    panel, parts, cb = _load("s1_strong_signal")
    m = _manifest("s1", panel)
    run = analyze(m, panel, parts, seed=SEED)
    B = m.reward_policy.budget_base_units

    agg = parts.groupby("cohort_id", sort=True)[
        ["accepted_observations", "quality_adjusted_observations"]
    ].sum()
    features = [
        CohortFeatures(
            cohort_id=cid,
            accepted_observations=int(row["accepted_observations"]),
            quality_adjusted_observations=int(row["quality_adjusted_observations"]),
            redundancy_score_micro=1_000_000,
        )
        for cid, row in agg.iterrows()
    ]
    causal = {c.cohort_id: c.budget_base_units for c in run.compilation.stage1.cohorts}

    totals = {}
    for name in BASELINES:
        alloc = allocate_baseline(name, features, B, causal_budgets=causal)
        assert sum(alloc.values()) <= B, "%s overspent the budget" % name
        totals[name] = sum(alloc.values())

    # The heuristics always spend (nearly) the whole budget; only the causal allocator can
    # decline to spend. That asymmetry is the point of the comparison, not a defect.
    assert totals["activity"] > 0.99 * B
    assert totals["quality"] > 0.99 * B
    assert totals["causal"] <= B


def test_causal_allocator_declines_to_spend_under_the_null() -> None:
    panel, parts, _ = _load("s2_null_effect")
    m = _manifest("s2", panel)
    run = analyze(m, panel, parts, seed=SEED)
    B = m.reward_policy.budget_base_units
    causal_total = sum(c.budget_base_units for c in run.compilation.stage1.cohorts)
    assert causal_total < B, (
        "under a true null the causal allocator should leave budget unspent; it spent %d of %d"
        % (causal_total, B)
    )
