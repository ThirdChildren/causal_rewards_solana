"""Scenario / data-generating-process sanity checks.

These are behavioral (not known-answer) checks: they assert the DGP produces the qualitative
structure each benchmark scenario is supposed to stress. Known-answer estimator tests land in
the causal engine (M3), which must RECOVER these truths from observed outcomes alone.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from depin_sim.config import load_scenario
from depin_sim.run import run_scenario

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"


def _run(name: str):
    return run_scenario(load_scenario(SCENARIO_DIR / name))


def test_cohort_level_estimand_shape():
    """Estimand grid is (cell x time_block); it must NOT be per-sensor."""
    r = _run("baseline_alpha.json")
    cb = r.artifact["content"]["cohort_blocks"]
    expected = r.network.n_cells * r.config.n_time_blocks
    assert len(cb["cell_id"]) == expected
    # More sensors than cohort-blocks — sensors are below the estimand line.
    assert r.network.n_sensors != expected


def test_null_scenario_has_zero_true_effect():
    r = _run("s2_null_effect.json")
    assert r.config.effect.true_effect == 0.0
    assert float(r.outcomes.cohort_effect.mean()) == 0.0
    # Observed treated vs control RMSE difference should be small (pure noise), no built-in gap.
    treated = r.outcomes.treated
    rmse = r.outcomes.rmse
    diff = rmse[treated].mean() - rmse[~treated].mean()
    assert abs(diff) < 0.05


def test_strong_signal_reduces_error_for_treated():
    r = _run("s1_strong_signal.json")
    rmse, treated = r.outcomes.rmse, r.outcomes.treated
    # Treated cohort-blocks have LOWER out-of-sample error on average.
    assert rmse[treated].mean() < rmse[~treated].mean()


def test_sybils_present_and_inflate_activity():
    r = _run("s5_sybil_contamination.json")
    assert r.network.sensor_is_sybil.any()
    assert 0.25 < float(r.network.sensor_is_sybil.mean()) < 0.45


def test_interference_biases_naive_effect_down():
    """With spillover, controls also improve, shrinking the naive treated-vs-control gap
    relative to the true mean cohort effect."""
    r = _run("s4_interference.json")
    rmse, treated = r.outcomes.rmse, r.outcomes.treated
    naive_gap = rmse[~treated].mean() - rmse[treated].mean()  # improvement attributed to treatment
    true_effect = float(r.outcomes.cohort_effect.mean())
    assert naive_gap < true_effect  # spillover contaminates controls -> attenuation


def test_guard_band_drops_contaminated_controls():
    r = _run("s4b_interference_guardband.json")
    assert not r.assignment.eligible.all()  # some units dropped by the guard band


def test_observational_replay_is_confounded():
    r = _run("s6_demand_shift.json")
    assert r.config.design == "observational_replay"
    # Treatment correlates with cohort info value (the confounder).
    treated_any = r.assignment.treated.any(axis=1)
    info = r.network.cell_info_value
    assert info[treated_any].mean() > info[~treated_any].mean()


def test_min_sample_flag_present():
    r = _run("baseline_alpha.json")
    cb = r.artifact["content"]["cohort_blocks"]
    assert set(np.unique(cb["meets_min_sample"])).issubset({True, False})


@pytest.mark.parametrize("scenario", sorted(SCENARIO_DIR.glob("*.json")), ids=lambda p: p.stem)
def test_all_scenarios_run_without_error(scenario):
    r = run_scenario(load_scenario(scenario))
    assert r.content_hash
    assert r.artifact["summary"]["total_signed_observations"] > 0
