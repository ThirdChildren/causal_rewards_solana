"""The COMPENSATION view (``crp_engine.studies`` compensation rows + ``docs/compensation-study.md``).

Answers the treasury owner's CONDITION 1: measure how much genuine signal is PAID, not just
detected, before fixing the recommended reward curve. These tests pin the new columns so the
finding — that a proportional recalibration UNDER-DEPLOYS on high signal while a 10%B cap does not —
cannot be quietly lost when the grid, seed, or renderer changes.

Study-only: nothing here touches a frozen default or the shipped reward goldens. The `shipped`
candidate curve is asserted to be the verbatim frozen engine deployment, so the compensation table
cannot silently drift from the shipped policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crp_engine.levers import cap_base_units, saturate_curve
from crp_engine.studies import (
    COMP_CAP_FINAL_PPM,
    render_compensation_markdown,
    run_study,
)


def _sim_ready() -> bool:
    repo = Path(__file__).resolve().parents[2]
    return (repo / "simulator" / "out" / "s2_null_effect" / "cohort_blocks.parquet").is_file()


pytestmark = pytest.mark.skipif(not _sim_ready(), reason="simulator outputs not generated")


CURVES = ("shipped", "recal_es", "recal_es+cap10", "cap10", "cap5", "cap2.5")
HIGH_SIGNAL = ("s1_strong_signal", "s5_sybil_contamination", "s4_interference")


def _by_scenario():
    return {s.scenario: s for s in run_study()}


def _row(st, scenario: str, curve: str):
    return next(c for c in st[scenario].compensation if c.curve == curve)


# ------------------------------------------------------------------ shape / determinism

def test_every_scenario_has_every_candidate_curve() -> None:
    st = _by_scenario()
    for s in st.values():
        got = {c.curve for c in s.compensation}
        assert got == set(CURVES), s.scenario


def test_compensation_markdown_is_byte_deterministic() -> None:
    a = render_compensation_markdown(run_study())
    b = render_compensation_markdown(run_study())
    assert a == b
    assert "The single finalized recommendation" in a


# ------------------------------------------------------------------ shipped == frozen policy

def test_shipped_curve_is_the_verbatim_frozen_deployment() -> None:
    """The `shipped` compensation row must equal the frozen `none` cell, so the table cannot drift."""
    st = _by_scenario()
    for s in st.values():
        none_cell = next(c for c in s.cells if c.regime == "none")
        shipped = _row(st, s.scenario, "shipped")
        assert shipped.deployed_ppm == none_cell.deployed_ppm
        assert shipped.max_share_ppm == none_cell.max_share_ppm
        assert shipped.n_paid == none_cell.n_paid
        assert shipped.scaled_to_budget == none_cell.scaled_to_budget


# ------------------------------------------------------------------ CONDITION 1: under-deployment

def test_equal_share_recalibration_underdeploys_on_every_high_signal_scenario() -> None:
    """The core CONDITION-1 finding: a proportional recalibration cuts legitimate payout hard."""
    st = _by_scenario()
    for scn in HIGH_SIGNAL:
        shipped = _row(st, scn, "shipped")
        recal = _row(st, scn, "recal_es")
        # head-count power is UNCHANGED (the metric that hid the cost) ...
        assert recal.power_ppm == shipped.power_ppm
        assert recal.n_paid == shipped.n_paid
        # ... but legitimate payout collapses, and the treasury recovers the difference.
        assert recal.legit_base_units < shipped.legit_base_units // 4
        assert recal.recovered_ppm > shipped.recovered_ppm


def test_proportional_rescale_scales_legit_and_ppute_by_the_same_factor() -> None:
    """A pure rescale is a ``value_scale`` change: legit and ppute move together, targeting does not.

    On the 60-cohort scenarios the equal-share scale is 1/12, so both legit and ppute drop ~12x.
    Their ratio is invariant up to integer rounding — the exposure changed, the efficiency did not.
    """
    st = _by_scenario()
    for scn in ("s1_strong_signal", "s5_sybil_contamination", "s4_interference"):
        shipped = _row(st, scn, "shipped")
        recal = _row(st, scn, "recal_es")
        # legit and ppute scale by the SAME factor (their ratio to each other is preserved).
        assert abs(
            shipped.legit_base_units * recal.ppute_base_per_effect
            - recal.legit_base_units * shipped.ppute_base_per_effect
        ) <= max(shipped.legit_base_units, recal.legit_base_units)


# ------------------------------------------------------------------ the finalized 10%B cap

def test_cap10_preserves_more_signal_than_recalibration_and_bounds_concentration() -> None:
    st = _by_scenario()
    for scn in HIGH_SIGNAL:
        cap10 = _row(st, scn, "cap10")
        recal = _row(st, scn, "recal_es")
        shipped = _row(st, scn, "shipped")
        # The cap keeps materially more legitimate payout than the recalibration ...
        assert cap10.legit_base_units > recal.legit_base_units
        # ... does not INCREASE deployment beyond the frozen policy (it only clips) ...
        assert cap10.legit_base_units <= shipped.legit_base_units
        # ... and bounds every single-cohort cheque to the cap, distribution-free.
        assert cap10.max_share_ppm <= COMP_CAP_FINAL_PPM


def test_cap10_cuts_null_waste_below_the_shipped_curve() -> None:
    st = _by_scenario()
    s2_shipped = _row(st, "s2_null_effect", "shipped")
    s2_cap = _row(st, "s2_null_effect", "cap10")
    assert s2_cap.waste_ppm < s2_shipped.waste_ppm
    assert s2_cap.max_share_ppm <= COMP_CAP_FINAL_PPM
    assert s2_cap.legit_base_units == 0  # nothing legitimate exists on a true-null scenario


def test_tighter_caps_underdeploy_signal_faster_than_they_cut_waste() -> None:
    """Why 10%B and not tighter: the frontier. Legit falls monotonically as the cap tightens."""
    st = _by_scenario()
    s1 = [_row(st, "s1_strong_signal", c).legit_base_units for c in ("cap10", "cap5", "cap2.5")]
    assert s1[0] > s1[1] > s1[2]
    s2 = [_row(st, "s2_null_effect", c).waste_ppm for c in ("cap10", "cap5", "cap2.5")]
    assert s2[0] > s2[1] > s2[2]
    # Targeting ratio (s2 waste / s1 legit) is best at 10%B and worsens as the cap bites signal.
    def ratio(cap: str) -> float:
        return (
            _row(st, "s2_null_effect", cap).waste_ppm
            / _row(st, "s1_strong_signal", cap).legit_ppm
        )
    assert ratio("cap10") < ratio("cap5") < ratio("cap2.5")


# ------------------------------------------------------------------ ppute definition

def test_ppute_is_undefined_on_null_scenarios_and_defined_on_positives() -> None:
    st = _by_scenario()
    for c in st["s2_null_effect"].compensation:
        assert c.ppute_base_per_effect == -1
    for c in st["s1_strong_signal"].compensation:
        assert c.ppute_base_per_effect >= 0


def test_ppute_denominator_is_mean_effect_times_payable_count() -> None:
    st = _by_scenario()
    s = st["s1_strong_signal"]
    assert s.true_effect_delivered_micro == s.mean_cohort_effect_micro * s.n_payable_true_positive
    shipped = _row(st, "s1_strong_signal", "shipped")
    expected = (shipped.legit_base_units * 1_000_000) // s.true_effect_delivered_micro
    assert shipped.ppute_base_per_effect == expected


# ------------------------------------------------------------------ finalized breakpoints (golden)

def test_finalized_curve_is_the_shipped_scale_saturated_at_10pct() -> None:
    """The single recommendation handed to the architect, pinned as a golden."""
    B = 100_000_000_000
    shipped_curve = (
        (0, 0),
        (100_000, 20_000_000_000),
        (500_000, 80_000_000_000),
        (1_000_000, 120_000_000_000),
    )
    ceiling = cap_base_units(B, COMP_CAP_FINAL_PPM)
    assert ceiling == 10_000_000_000
    assert saturate_curve(shipped_curve, ceiling) == (
        (0, 0),
        (50_000, 10_000_000_000),
        (100_000, 10_000_000_000),
        (500_000, 10_000_000_000),
        (1_000_000, 10_000_000_000),
    )


def test_headline_compensation_goldens() -> None:
    """Pin the exact numbers the verdict quotes, so the columns themselves are under test."""
    st = _by_scenario()
    assert _row(st, "s1_strong_signal", "shipped").legit_base_units == 73_751_750_000
    assert _row(st, "s1_strong_signal", "recal_es").legit_base_units == 6_145_979_168
    assert _row(st, "s1_strong_signal", "cap10").legit_base_units == 55_902_600_000
    assert _row(st, "s5_sybil_contamination", "cap10").legit_base_units == 54_608_800_000
    assert _row(st, "s2_null_effect", "shipped").waste_ppm == 296_132
    assert _row(st, "s2_null_effect", "cap10").waste_ppm == 136_768
