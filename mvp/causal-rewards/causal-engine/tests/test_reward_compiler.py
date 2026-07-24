"""Stage-1 / Stage-2 reward compiler: the worked example, the invariants, the guards."""

from __future__ import annotations

import pytest

from crp_engine.estimators import CohortEffect
from crp_engine.manifest import Manifest, ManifestError
from crp_engine.panel import CohortSample, IdentificationMode
from crp_engine.reward_compiler import (
    ParticipantRow,
    compile_rewards,
    improvement_from_effect,
    stage1_valuation,
    stage2_split,
)


def _sample(cid: str, *, eligible=True) -> CohortSample:
    return CohortSample(
        cohort_id=cid,
        n_units_min=10 if eligible else 1,
        n_observations=1000 if eligible else 5,
        n_time_blocks=48 if eligible else 2,
        n_treated_blocks=24,
        n_control_blocks=24,
        eligible=eligible,
        reasons=() if eligible else ("below_min_units_per_cohort",),
    )


def _effect(cid: str, effect: float, se: float, identified=True) -> CohortEffect:
    return CohortEffect(cid, effect, se, 48, 24, identified, "within_cohort")


@pytest.fixture
def worked_manifest(manifest_obj) -> Manifest:
    """The reward-policy.md worked example has only 3 cohorts; relax min_eligible_cohorts."""
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "1"
    return Manifest.from_obj(manifest_obj)


# ------------------------------------------------------------------ Stage 1

def test_stage1_reproduces_the_reward_policy_worked_example(worked_manifest) -> None:
    """reward-policy.md "Worked example": A pays 30_260_000_000, B and C pay 0."""
    effects = {
        "A": _effect("A", -0.30, 0.08),   # improvement 300000, se 80000
        "B": _effect("B", -0.05, 0.06),   # improvement  50000, se 60000 -> LCB <= 0
        "C": _effect("C", -0.40, 0.05),   # strong point estimate but FAILS min-sample
    }
    samples = {"A": _sample("A"), "B": _sample("B"), "C": _sample("C", eligible=False)}
    s1 = stage1_valuation(worked_manifest, effects, samples)
    by = {c.cohort_id: c for c in s1.cohorts}

    assert by["A"].improvement_s == 300_000
    assert by["A"].se_s == 80_000
    assert by["A"].margin_s == 131_600          # round_he(1_645_000 * 80_000 / 1e6)
    assert by["A"].conservative_s == 168_400
    assert by["A"].alloc_base_units == 30_260_000_000

    assert by["B"].conservative_s == 0          # lower bound <= 0 (Invariant 3)
    assert by["B"].alloc_base_units == 0

    assert by["C"].conservative_s == 0          # forced by the minimum-sample rule
    assert by["C"].alloc_base_units == 0
    assert "below_min_units_per_cohort" in by["C"].reasons

    assert s1.total_budget_allocated == 30_260_000_000
    assert not s1.scaled_to_budget
    assert s1.budget_base_units - s1.total_budget_allocated == 69_740_000_000


def test_stage2_reproduces_the_worked_example_leaves(worked_manifest) -> None:
    effects = {"A": _effect("A", -0.30, 0.08)}
    samples = {"A": _sample("A")}
    s1 = stage1_valuation(worked_manifest, effects, samples)
    p1, p2 = b"\x01" * 32, b"\x02" * 32
    rows = stage2_split(
        worked_manifest,
        s1,
        [
            ParticipantRow("A", p1, {"quality_adjusted_observations": 500 * 900_000}),
            ParticipantRow("A", p2, {"quality_adjusted_observations": 300 * 800_000}),
        ],
    )
    amounts = {r.recipient: r.amount_base_units for r in rows}
    assert amounts[p1] == 19_734_782_608
    assert amounts[p2] == 10_525_217_391
    assert sum(amounts.values()) == 30_259_999_999  # dust of 1 base unit, recoverable
    assert sum(amounts.values()) <= s1.total_budget_allocated


# ------------------------------------------------------------------ Invariant 3 guards

def test_no_positive_payout_when_conservative_bound_is_zero(worked_manifest) -> None:
    effects = {"X": _effect("X", -0.001, 0.5)}   # huge SE
    s1 = stage1_valuation(worked_manifest, effects, {"X": _sample("X")})
    assert s1.cohorts[0].conservative_s == 0
    assert s1.cohorts[0].budget_base_units == 0


def test_no_positive_payout_when_min_sample_fails(worked_manifest) -> None:
    effects = {"X": _effect("X", -0.90, 0.001)}  # overwhelming evidence
    s1 = stage1_valuation(worked_manifest, effects, {"X": _sample("X", eligible=False)})
    assert s1.cohorts[0].conservative_s == 0
    assert s1.cohorts[0].budget_base_units == 0


def test_no_positive_payout_when_effect_is_not_identified(worked_manifest) -> None:
    effects = {"X": _effect("X", -0.90, 0.001, identified=False)}
    s1 = stage1_valuation(worked_manifest, effects, {"X": _sample("X")})
    assert s1.cohorts[0].conservative_s == 0
    assert "per_cohort_effect_not_identified" in s1.cohorts[0].reasons


def test_wrong_sign_effect_never_pays(worked_manifest) -> None:
    """A cohort that made prediction error WORSE must pay nothing."""
    effects = {"X": _effect("X", +0.40, 0.01)}
    s1 = stage1_valuation(worked_manifest, effects, {"X": _sample("X")})
    assert s1.cohorts[0].improvement_s == -400_000
    assert s1.cohorts[0].conservative_s == 0


def test_whole_distribution_is_null_below_min_eligible_cohorts(manifest_obj) -> None:
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "10"
    m = Manifest.from_obj(manifest_obj)
    effects = {"A": _effect("A", -0.30, 0.01), "B": _effect("B", -0.30, 0.01)}
    s1 = stage1_valuation(m, effects, {"A": _sample("A"), "B": _sample("B")})
    assert s1.null_distribution
    assert all(c.conservative_s == 0 and c.budget_base_units == 0 for c in s1.cohorts)
    assert s1.total_budget_allocated == 0
    assert any("min_eligible_cohorts" in r for r in s1.null_reasons)


def test_observational_replay_pays_nothing(manifest_obj) -> None:
    manifest_obj["design"]["template"] = "observational_replay"
    manifest_obj["design"]["eligible_for_strong_causal_claim"] = False
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "1"
    m = Manifest.from_obj(manifest_obj)
    s1 = stage1_valuation(m, {"A": _effect("A", -0.9, 0.001)}, {"A": _sample("A")})
    assert s1.null_distribution
    assert any("eligible_for_strong_causal_claim" in r for r in s1.null_reasons)


# ------------------------------------------------------------------ budget guarantee

def test_budget_cap_scales_proportionally_and_never_overshoots(manifest_obj) -> None:
    manifest_obj["reward_policy"]["budget_base_units"] = "1000"
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "1"
    m = Manifest.from_obj(manifest_obj)
    effects = {"c%02d" % i: _effect("c%02d" % i, -0.9, 0.001) for i in range(20)}
    samples = {cid: _sample(cid) for cid in effects}
    s1 = stage1_valuation(m, effects, samples)
    assert s1.scaled_to_budget
    assert s1.total_budget_allocated <= 1000
    assert s1.total_alloc_before_cap > 1000


def test_end_to_end_total_never_exceeds_budget(worked_manifest) -> None:
    effects = {"c%d" % i: _effect("c%d" % i, -0.5 - 0.01 * i, 0.02) for i in range(8)}
    samples = {cid: _sample(cid) for cid in effects}
    parts = [
        ParticipantRow(cid, bytes([i + 1]) * 32, {"quality_adjusted_observations": 1000 * (i + 1)})
        for cid in effects
        for i in range(4)
    ]
    comp = compile_rewards(worked_manifest, effects, samples, parts)
    assert comp.total_leaf_base_units <= worked_manifest.reward_policy.budget_base_units
    assert comp.total_leaf_base_units == sum(lf.amount_base_units for lf in comp.leaves)
    # aggregate shape: exactly one leaf per distinct recipient
    assert len({lf.recipient for lf in comp.leaves}) == len(comp.leaves)
    assert [lf.leaf_index for lf in comp.leaves] == list(range(len(comp.leaves)))


def test_zero_weight_participants_get_nothing_and_are_omitted(worked_manifest) -> None:
    effects = {"A": _effect("A", -0.30, 0.08)}
    samples = {"A": _sample("A")}
    live, dead = b"\xaa" * 32, b"\xbb" * 32
    comp = compile_rewards(
        worked_manifest, effects, samples,
        [
            ParticipantRow("A", live, {"quality_adjusted_observations": 1_000_000}),
            ParticipantRow("A", dead, {"quality_adjusted_observations": 0}),
        ],
    )
    assert [lf.recipient for lf in comp.leaves] == [live]
    assert comp.dropped_zero_sum_recipients == (dead,)


def test_null_distribution_yields_the_empty_reward_tree(manifest_obj) -> None:
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "99"
    m = Manifest.from_obj(manifest_obj)
    comp = compile_rewards(
        m, {"A": _effect("A", -0.9, 0.001)}, {"A": _sample("A")},
        [ParticipantRow("A", b"\x05" * 32, {"quality_adjusted_observations": 10})],
    )
    assert comp.reward_root_hex == "00" * 32
    assert comp.leaf_count == 0
    assert comp.total_leaf_base_units == 0


# ------------------------------------------------------------------ CRP-WS1

def test_weight_formula_rejects_attributes_outside_the_vocabulary(manifest_obj) -> None:
    manifest_obj["reward_policy"]["intra_cohort_split"]["weight_formula"] = "1*total_revenue"
    with pytest.raises(ManifestError, match="closed CRP-WS1"):
        Manifest.from_obj(manifest_obj)


def test_weight_formula_rejects_a_product_of_two_attributes(manifest_obj) -> None:
    manifest_obj["reward_policy"]["intra_cohort_split"]["weight_formula"] = (
        "1*accepted_observations*uptime_micro"
    )
    with pytest.raises(ManifestError):
        Manifest.from_obj(manifest_obj)


def test_weight_formula_rejects_duplicate_attributes(manifest_obj) -> None:
    manifest_obj["reward_policy"]["intra_cohort_split"]["weight_formula"] = (
        "1*uptime_micro + 2*uptime_micro"
    )
    with pytest.raises(ManifestError, match="repeats attribute"):
        Manifest.from_obj(manifest_obj)


def test_multi_term_weight_formula(manifest_obj) -> None:
    manifest_obj["reward_policy"]["intra_cohort_split"]["weight_formula"] = (
        "2*accepted_observations + 3*uptime_micro"
    )
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "1"
    m = Manifest.from_obj(manifest_obj)
    s1 = stage1_valuation(m, {"A": _effect("A", -0.30, 0.08)}, {"A": _sample("A")})
    rows = stage2_split(
        m, s1,
        [
            ParticipantRow("A", b"\x01" * 32, {"accepted_observations": 10, "uptime_micro": 100}),
            ParticipantRow("A", b"\x02" * 32, {"accepted_observations": 0, "uptime_micro": 0}),
        ],
    )
    assert rows[0].weight == 2 * 10 + 3 * 100
    assert rows[1].weight == 0
    assert rows[0].amount_base_units == s1.cohorts[0].budget_base_units
    assert rows[1].amount_base_units == 0


def test_missing_required_attribute_is_an_error(worked_manifest) -> None:
    s1 = stage1_valuation(worked_manifest, {"A": _effect("A", -0.30, 0.08)}, {"A": _sample("A")})
    with pytest.raises(ValueError, match="missing CRP-WS1 attribute"):
        stage2_split(worked_manifest, s1, [ParticipantRow("A", b"\x01" * 32, {"uptime_micro": 1})])


def test_duplicate_participant_within_a_cohort_is_rejected(worked_manifest) -> None:
    s1 = stage1_valuation(worked_manifest, {"A": _effect("A", -0.30, 0.08)}, {"A": _sample("A")})
    with pytest.raises(ValueError, match="duplicate recipient"):
        stage2_split(
            worked_manifest, s1,
            [
                ParticipantRow("A", b"\x01" * 32, {"quality_adjusted_observations": 1}),
                ParticipantRow("A", b"\x01" * 32, {"quality_adjusted_observations": 2}),
            ],
        )


# ------------------------------------------------------------------ transform guards

def test_transform_rejects_a_direction_that_would_pay_for_a_worse_outcome(manifest_obj) -> None:
    manifest_obj["primary_outcome"]["improvement_direction"] = "increase"
    m = Manifest.from_obj(manifest_obj)  # transform is still negate_then_clamp
    with pytest.raises(ValueError, match="worse outcome"):
        improvement_from_effect(-300_000, m)


def test_signed_transform_follows_improvement_direction(manifest_obj) -> None:
    manifest_obj["reward_policy"]["positive_improvement_transform"]["type"] = "signed"
    m_dec = Manifest.from_obj(manifest_obj)
    assert improvement_from_effect(-300_000, m_dec) == 300_000
    manifest_obj["primary_outcome"]["improvement_direction"] = "increase"
    m_inc = Manifest.from_obj(manifest_obj)
    assert improvement_from_effect(300_000, m_inc) == 300_000
