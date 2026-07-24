"""Sensitivity analyses and balance checks — descriptive guardrails, never payout gates."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from crp_engine.balance import balance_report, threshold_micro
from crp_engine.manifest import Manifest
from crp_engine.panel import load_panel
from crp_engine.sensitivity import rademacher_stream, run_sensitivity

SEED = bytes.fromhex("11" * 32)


def _panel_frame(true_effect=0.12, n_cohorts=16, n_blocks=16, seed=8, alternate=True):
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_cohorts):
        shock = rng.normal(0, 0.3)
        phase = int(rng.integers(0, 2))
        for t in range(n_blocks):
            treated = ((t + phase) % 2) == 1 if alternate else bool(rng.integers(0, 2))
            rows.append(
                {
                    "cohort_id": "geo%02d" % c,
                    "time_block": t,
                    "arm": "treatment" if treated else "control",
                    "outcome": 1.0 + shock - (true_effect if treated else 0.0)
                    + rng.normal(0, 0.05),
                    "n_units": 10,
                    "n_observations": 300,
                }
            )
    return pd.DataFrame(rows)


def _m(manifest_obj, analyses):
    manifest_obj["analysis_plan"]["sensitivity_analyses"] = analyses
    manifest_obj["analysis_plan"]["covariate_adjustment"] = []
    manifest_obj["analysis_plan"]["minimum_sample"] = {
        "min_units_per_cohort": "5",
        "min_observations_per_cohort": "1000",
        "min_time_blocks": "8",
        "min_eligible_cohorts": "10",
    }
    return Manifest.from_obj(manifest_obj)


def test_leave_one_cohort_out_reports_a_range(manifest_obj) -> None:
    m = _m(manifest_obj, ["leave_one_cohort_out"])
    panel = load_panel(_panel_frame(), m)
    (res,) = run_sensitivity(panel, seed=SEED)
    assert res.status == "ok"
    assert res.kind == "descriptive"
    assert res.values["n_refits"] == 16
    assert res.values["min_effect"] <= res.values["full_sample_effect"] <= res.values["max_effect"]


def test_placebo_is_reported_as_uninformative_for_period_one_alternation(manifest_obj) -> None:
    """Honest reporting: a one-block rotation of a period-1 switchback is degenerate."""
    m = _m(manifest_obj, ["placebo_time_shift"])
    panel = load_panel(_panel_frame(alternate=True), m)
    (res,) = run_sensitivity(panel, seed=SEED)
    assert res.status == "skipped"
    assert "uninformative by construction" in res.note


def test_placebo_runs_on_a_non_alternating_schedule(manifest_obj) -> None:
    m = _m(manifest_obj, ["placebo_time_shift"])
    panel = load_panel(_panel_frame(alternate=False), m)
    (res,) = run_sensitivity(panel, seed=SEED)
    assert res.status == "ok"
    assert abs(res.values["placebo_effect"]) < abs(res.values["real_effect"])


def test_wild_cluster_bootstrap_rejects_under_a_real_effect(manifest_obj) -> None:
    m = _m(manifest_obj, ["wild_cluster_bootstrap"])
    panel = load_panel(_panel_frame(true_effect=0.20), m)
    (res,) = run_sensitivity(panel, seed=SEED)
    assert res.status == "ok"
    assert res.values["p_value"] < 0.05
    assert res.values["weights"] == "rademacher_two_point"
    assert res.values["null"] == "restricted"


def test_wild_cluster_bootstrap_does_not_reject_under_the_null(manifest_obj) -> None:
    m = _m(manifest_obj, ["wild_cluster_bootstrap"])
    panel = load_panel(_panel_frame(true_effect=0.0, seed=404), m)
    (res,) = run_sensitivity(panel, seed=SEED)
    assert res.status == "ok"
    assert res.values["p_value"] > 0.05


def test_wild_cluster_bootstrap_is_seed_deterministic(manifest_obj) -> None:
    m = _m(manifest_obj, ["wild_cluster_bootstrap"])
    panel = load_panel(_panel_frame(), m)
    a = run_sensitivity(panel, seed=SEED)[0].values["p_value"]
    b = run_sensitivity(panel, seed=SEED)[0].values["p_value"]
    c = run_sensitivity(panel, seed=bytes(32))[0].values["p_value"]
    assert a == b
    assert isinstance(c, float)


def test_spillover_is_surfaced_when_adjacency_is_supplied(manifest_obj) -> None:
    """DePIN cohorts interfere: with real spillover the naive effect is biased, and we say so."""
    m = _m(manifest_obj, ["interference_spillover"])
    rng = np.random.default_rng(2024)
    n_c, n_t = 20, 16
    treated = rng.integers(0, 2, size=(n_c, n_t)).astype(bool)
    adjacency = {"geo%02d" % c: ["geo%02d" % ((c + 1) % n_c), "geo%02d" % ((c - 1) % n_c)]
                 for c in range(n_c)}
    rows = []
    for c in range(n_c):
        shock = rng.normal(0, 0.2)
        for t in range(n_t):
            nbr_share = float(
                treated[(c + 1) % n_c, t] + treated[(c - 1) % n_c, t]
            ) / 2.0
            rows.append(
                {
                    "cohort_id": "geo%02d" % c,
                    "time_block": t,
                    "arm": "treatment" if treated[c, t] else "control",
                    "outcome": 1.0 + shock - 0.15 * treated[c, t] - 0.10 * nbr_share
                    + rng.normal(0, 0.03),
                    "n_units": 10,
                    "n_observations": 300,
                }
            )
    panel = load_panel(pd.DataFrame(rows), m)
    (res,) = run_sensitivity(panel, seed=SEED, adjacency=adjacency)
    assert res.status == "ok"
    assert res.values["spillover_coefficient"] == pytest.approx(-0.10, abs=0.05)
    assert res.values["direct_effect_adjusted"] == pytest.approx(-0.15, abs=0.05)


def test_spillover_is_skipped_without_adjacency(manifest_obj) -> None:
    m = _m(manifest_obj, ["interference_spillover"])
    panel = load_panel(_panel_frame(), m)
    (res,) = run_sensitivity(panel, seed=SEED)
    assert res.status == "skipped"
    assert "adjacency" in res.note


def test_unknown_sensitivity_is_reported_not_silently_dropped(manifest_obj) -> None:
    m = _m(manifest_obj, ["some_future_method"])
    panel = load_panel(_panel_frame(), m)
    (res,) = run_sensitivity(panel, seed=SEED)
    assert res.status == "unsupported"


def test_rademacher_weights_are_balanced_enough() -> None:
    draws = [rademacher_stream(SEED, 64, rep) for rep in range(200)]
    flat = [v for d in draws for v in draws[0] and d]
    share_plus = sum(1 for v in flat if v > 0) / len(flat)
    assert 0.45 < share_plus < 0.55


# ------------------------------------------------------------------ balance

def test_balance_threshold_parsing() -> None:
    assert threshold_micro("standardized_mean_difference_max_100000") == 100_000
    assert threshold_micro("standardized_mean_difference_max_50000") == 50_000
    assert threshold_micro(None) == 100_000
    assert threshold_micro("something_else") == 100_000


def test_balance_flags_a_deliberately_imbalanced_covariate() -> None:
    rows = []
    for c in range(20):
        treated = c % 2 == 0
        for t in range(10):
            rows.append(
                {
                    "arm": "treatment" if treated else "control",
                    "outcome": 1.0,
                    # n_observations differs sharply by arm: an exposure-size imbalance.
                    "n_observations": 900 if treated else 100,
                    "n_units": 10,
                }
            )
    rep = balance_report(pd.DataFrame(rows), [])
    assert not rep.passed
    bad = next(i for i in rep.items if i.name == "n_observations")
    assert abs(bad.smd) > 0.1


def test_balance_passes_on_a_balanced_panel() -> None:
    frame = _panel_frame()
    rep = balance_report(frame, [])
    assert rep.passed
    assert rep.arm_share_treated_micro == pytest.approx(500_000, abs=20_000)


def test_balance_never_gates_payout(manifest_obj) -> None:
    """A balance failure must NOT zero an allocation — the frozen gates are min-sample and LCB."""
    from crp_engine.estimators import CohortEffect
    from crp_engine.panel import CohortSample
    from crp_engine.reward_compiler import stage1_valuation

    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "1"
    m = Manifest.from_obj(manifest_obj)
    s1 = stage1_valuation(
        m,
        {"A": CohortEffect("A", -0.30, 0.08, 48, 24, True, "within_cohort")},
        {"A": CohortSample("A", 10, 1000, 48, 24, 24, True, ())},
    )
    assert s1.cohorts[0].alloc_base_units == 30_260_000_000
