"""Artifact schema + canonical-encoding tests for analysis.json / rewards.parquet."""

from __future__ import annotations

import json

import pyarrow.parquet as pq
import pytest

from crp_engine.artifacts import ANALYSIS_SCHEMA, LEAVES_SCHEMA, REWARDS_SCHEMA
from crp_engine.demo import write_demo
from crp_engine.manifest import Manifest
from crp_engine.run import analyze, write_all
from tests.conftest import SPEC_MANIFEST

SEED = bytes.fromhex("00" * 24 + "0123456789abcdef")


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory):
    d = tmp_path_factory.mktemp("artifacts")
    spec = json.loads(SPEC_MANIFEST.read_text(encoding="utf-8"))
    paths = write_demo(d, spec, SEED)
    m = Manifest.from_path(paths["manifest"])
    run = analyze(m, paths["panel"], paths["participants"], seed=SEED)
    out = d / "out"
    hashes = write_all(run, out)
    return run, out, hashes


def test_analysis_top_level_schema(demo_run) -> None:
    run, out, _ = demo_run
    obj = run.analysis
    assert obj["schema"] == ANALYSIS_SCHEMA
    assert set(obj) == {
        "schema", "spec_version", "experiment_id", "manifest_hash", "engine", "estimand",
        "design", "analysis_plan", "identification", "primary_estimate", "balance",
        "sensitivity", "cohorts", "excluded_records", "reward_summary",
    }
    assert obj["manifest_hash"].startswith("sha256:")
    assert obj["engine"]["analysis_container_digest"].startswith("sha256:")
    assert obj["engine"]["reference_source_digest"].startswith("sha256:")


def test_exactly_one_primary_estimate(demo_run) -> None:
    """One primary outcome, one primary estimate; everything else is descriptive."""
    run, _, _ = demo_run
    assert isinstance(run.analysis["primary_estimate"], dict)
    assert run.analysis["primary_estimate"]["term"] == "treated"
    assert all(s["kind"] == "descriptive" for s in run.analysis["sensitivity"])


def test_every_cohort_row_carries_the_full_valuation_chain(demo_run) -> None:
    run, _, _ = demo_run
    for c in run.analysis["cohorts"]:
        assert set(c) >= {
            "cohort_id", "effect_s", "standard_error_s", "improvement_s", "margin_s",
            "conservative_effect_s", "allocation_base_units", "budget_base_units",
            "identified", "meets_minimum_sample", "exclusion_reasons",
        }
        # The conservative bound is reproducible from the published effect/SE/critical value.
        cv = int(run.analysis["analysis_plan"]["critical_value_micro"])
        from crp_engine.numeric import round_half_even_div

        margin = round_half_even_div(cv * int(c["standard_error_s"]), 1_000_000)
        assert int(c["margin_s"]) == margin
        expected = max(0, int(c["improvement_s"]) - margin)
        if c["identified"] == "true" and c["meets_minimum_sample"] == "true":
            assert int(c["conservative_effect_s"]) == expected


def test_reward_summary_is_internally_consistent(demo_run) -> None:
    run, _, _ = demo_run
    rs = run.analysis["reward_summary"]
    assert int(rs["total_leaf_base_units"]) <= int(rs["total_cohort_budget_base_units"])
    assert int(rs["total_cohort_budget_base_units"]) <= int(rs["budget_base_units"])
    assert int(rs["recoverable_base_units"]) == int(rs["budget_base_units"]) - int(
        rs["total_leaf_base_units"]
    )
    assert rs["leaf_set_shape"] == "aggregate_one_leaf_per_recipient"
    assert len(rs["reward_root_hex"]) == 64


def test_rewards_parquet_schema(demo_run) -> None:
    _, out, _ = demo_run
    t = pq.read_table(out / "rewards.parquet")
    assert t.schema.names == [
        "cohort_id", "recipient_hex", "weight", "cohort_weight_total",
        "cohort_budget_base_units", "amount_base_units",
        "recipient_aggregate_base_units", "leaf_index", "included_in_leaf_set",
    ]
    mirror = json.loads((out / "rewards.canonical.json").read_text(encoding="utf-8"))
    assert mirror["schema"] == REWARDS_SCHEMA
    assert len(mirror["rows"]) == t.num_rows


def test_reward_leaves_parquet_matches_the_committed_root(demo_run) -> None:
    run, out, _ = demo_run
    t = pq.read_table(out / "reward_leaves.parquet")
    assert t.schema.names == ["leaf_index", "recipient_hex", "amount_base_units", "leaf_hash_hex"]
    mirror = json.loads((out / "reward_leaves.canonical.json").read_text(encoding="utf-8"))
    assert mirror["schema"] == LEAVES_SCHEMA
    assert mirror["reward_root_hex"] == run.compilation.reward_root_hex
    # Recompute the root from the published leaves alone.
    from crp_engine.reference import RewardLeaf, reward_root

    leaves = [
        RewardLeaf(bytes.fromhex(r["recipient_hex"]), int(r["amount_base_units"]),
                   int(r["leaf_index"]))
        for r in mirror["leaves"]
    ]
    assert reward_root(leaves).hex() == run.compilation.reward_root_hex


def test_rewards_detail_aggregates_to_the_leaves(demo_run) -> None:
    run, out, _ = demo_run
    t = pq.read_table(out / "rewards.parquet").to_pylist()
    agg: dict[str, int] = {}
    for row in t:
        agg[row["recipient_hex"]] = agg.get(row["recipient_hex"], 0) + row["amount_base_units"]
    leaves = {lf.recipient.hex(): lf.amount_base_units for lf in run.compilation.leaves}
    assert {k: v for k, v in agg.items() if v != 0} == leaves


def test_provenance_carries_no_wall_clock(demo_run) -> None:
    _, out, _ = demo_run
    prov = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    joined = json.dumps(prov).lower()
    for banned in ("timestamp", "generated_at", "executed_at", "wall_clock", "now"):
        assert banned not in joined


def test_engine_hashes_file_lists_every_committed_hash(demo_run) -> None:
    _, out, hashes = demo_run
    obj = json.loads((out / "engine_hashes.json").read_text(encoding="utf-8"))
    assert obj["analysis.json"] == hashes["analysis.json"]
    assert obj["reward_root_hex"] == hashes["reward_root_hex"]
