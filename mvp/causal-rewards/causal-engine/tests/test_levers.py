"""The STUDY-ONLY spend levers (``crp_engine.levers``) and their identities in the arm study.

Three kinds of coverage here:

1. **Known answers** for each lever primitive on hand-computed integers (no simulator).
2. **Arm identities** — the study's arms 1/2 must be the verbatim frozen engine output and the
   verbatim BH regime cell, so the comparison table cannot silently drift from the shipped policy.
3. **The load-bearing claim**: a per-cohort cap applied post-hoc is reproduced EXACTLY by a
   saturating reward curve, i.e. the cap needs no new frozen manifest field.

Nothing here touches a frozen default; ``selected_cohorts=None`` remains the shipped behavior and
is asserted elsewhere (``tests/test_multiplicity.py``) plus by the reward goldens.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crp_engine.levers import (
    CAP_GRID_PPM,
    CURVE_REFERENCE_X,
    CURVE_SCALE_GRID,
    FLOOR_GRID_S,
    cap_base_units,
    capped_budgets,
    capped_overflowed,
    equal_share_scale,
    floor_selected,
    format_cap,
    format_floor,
    format_scale,
    rescale_curve,
    saturate_curve,
)
from crp_engine.numeric import piecewise_linear

#: The benchmark curve from ``specs/examples/manifest.example.json`` and its budget.
CURVE: tuple[tuple[int, int], ...] = (
    (0, 0),
    (100_000, 20_000_000_000),
    (500_000, 80_000_000_000),
    (1_000_000, 120_000_000_000),
)
B = 100_000_000_000


# ------------------------------------------------------------------ floor

def test_floor_selects_at_or_above_and_drops_zero() -> None:
    cons = {"a": 150_000, "b": 50_000, "c": 49_999, "d": 0}
    assert floor_selected(cons, 50_000) == frozenset({"a", "b"})   # >= is inclusive
    assert floor_selected(cons, 0) == frozenset({"a", "b", "c"})   # zero never earns
    with pytest.raises(ValueError):
        floor_selected(cons, -1)


def test_floor_composes_with_a_base_selection_as_intersection() -> None:
    cons = {"a": 150_000, "b": 50_000, "c": 10_000}
    base = frozenset({"b", "c"})
    assert floor_selected(cons, 20_000, base=base) == frozenset({"b"})
    # Order of application does not matter: a cohort's conservative_s is independent of selection.
    assert floor_selected(cons, 20_000) & base == floor_selected(cons, 20_000, base=base)


# ------------------------------------------------------------------ cap

def test_cap_base_units_is_exact_integer_ppm() -> None:
    assert cap_base_units(B, 100_000) == 10_000_000_000     # 10% of B
    assert cap_base_units(B, 25_000) == 2_500_000_000       # 2.5% of B
    assert cap_base_units(B, 0) == 0
    with pytest.raises(ValueError):
        cap_base_units(B, -1)


def test_capped_budgets_clips_and_does_not_redistribute() -> None:
    allocs = [("a", 40_000_000_000), ("b", 5_000_000_000)]
    out = capped_budgets(allocs, B, 100_000)                 # cap = 10e9
    assert out == {"a": 10_000_000_000, "b": 5_000_000_000}
    # The 30e9 clipped off "a" is RECOVERED, never handed to "b".
    assert sum(out.values()) == 15_000_000_000
    assert not capped_overflowed(allocs, B, 100_000)


def test_capped_budgets_still_applies_the_frozen_overflow_rule() -> None:
    # Twelve cohorts at the 10% cap sum to 120% of B -> the S > B branch must fire.
    allocs = [("c%02d" % i, 40_000_000_000) for i in range(12)]
    assert capped_overflowed(allocs, B, 100_000)
    out = capped_budgets(allocs, B, 100_000)
    assert sum(out.values()) <= B
    assert len(set(out.values())) == 1                       # pro-rata is uniform here


# ------------------------------------------------------------------ curve recalibration

def test_rescale_curve_is_exact_and_monotone() -> None:
    out = rescale_curve(CURVE, 1, 4)
    assert out == ((0, 0), (100_000, 5_000_000_000), (500_000, 20_000_000_000),
                   (1_000_000, 30_000_000_000))
    assert all(y1 >= y0 for (_, y0), (_, y1) in zip(out, out[1:]))
    with pytest.raises(ValueError):
        rescale_curve(CURVE, 0, 4)


def test_rescale_curve_rounds_half_to_even() -> None:
    # y=5 at x=1: 5/2 = 2.5 -> 2 (ties to even). y=15 at x=2: 7.5 -> 8.
    assert rescale_curve(((0, 0), (1, 5), (2, 15)), 1, 2) == ((0, 0), (1, 2), (2, 8))


def test_equal_share_scale_is_the_documented_five_over_n() -> None:
    # curve(x_ref) == B/5 on the benchmark curve, so the calibrated scale is exactly 5/N.
    assert piecewise_linear(CURVE_REFERENCE_X, CURVE) * 5 == B
    for n, expected in ((60, (1, 12)), (20, (1, 4)), (10, (1, 2))):
        num, den = equal_share_scale(CURVE, B, n)
        assert num * expected[1] == den * expected[0]
    # And every calibrated point for the benchmark's cohort counts is on the swept grid.
    assert (1, 12) in CURVE_SCALE_GRID and (1, 4) in CURVE_SCALE_GRID
    with pytest.raises(ValueError):
        equal_share_scale(CURVE, B, 0)


def test_equal_share_scale_makes_n_reference_cohorts_exhaust_the_budget() -> None:
    """``N * curve(x_ref) == B``, up to the single half-even rounding applied to one breakpoint.

    ``B / (N * y_ref)`` need not be exact in base units (here 20e9/12 = 1_666_666_666.67), so the
    calibrated curve can be off by at most one rounding step per cohort — 20 base units out of
    100e9. Asserting exact equality would be asserting that the budget divides evenly.
    """
    n = 60
    num, den = equal_share_scale(CURVE, B, n)
    calibrated = rescale_curve(CURVE, num, den)
    assert abs(n * piecewise_linear(CURVE_REFERENCE_X, calibrated) - B) <= n


@pytest.mark.parametrize("cap_ppm", CAP_GRID_PPM)
def test_saturating_curve_never_overpays_the_cap(cap_ppm: int) -> None:
    ceiling = cap_base_units(B, cap_ppm)
    sat = saturate_curve(CURVE, ceiling)
    # Still a valid piecewise_linear_monotonic curve per the frozen schema rules.
    assert sat[0] == (0, 0)
    assert all(x1 > x0 for (x0, _), (x1, _) in zip(sat, sat[1:]))
    assert all(y1 >= y0 for (_, y0), (_, y1) in zip(sat, sat[1:]))
    for x in range(0, 1_100_001, 997):
        assert piecewise_linear(x, sat) <= min(piecewise_linear(x, CURVE), ceiling)


@pytest.mark.parametrize("cap_ppm", (100_000, 50_000, 25_000))
def test_saturating_curve_reproduces_the_cap_exactly_at_integral_crossings(cap_ppm: int) -> None:
    """THE claim: a per-cohort cap is a reward-curve shape, not a new frozen field.

    On the benchmark curve the crossing point is integral for these ceilings, so the saturating
    curve equals ``min(curve(x), ceiling)`` at EVERY integer x — the cap exactly, with no schema
    change. (At ``25.0%B`` the crossing is not integral; that case is covered by the
    never-overpays test above.)
    """
    ceiling = cap_base_units(B, cap_ppm)
    sat = saturate_curve(CURVE, ceiling)
    for x in range(0, 1_100_001):
        assert piecewise_linear(x, sat) == min(piecewise_linear(x, CURVE), ceiling)


# ------------------------------------------------------------------ formatting (deterministic text)

def test_formatters_are_exact_and_float_free() -> None:
    assert format_floor(30_000) == "0.030000"
    assert format_floor(1_500_000) == "1.500000"
    assert format_floor(0) == "0.000000"
    assert format_cap(250_000) == "25.0%B"
    assert format_cap(25_000) == "2.5%B"
    assert format_scale(1, 12) == "x1/12"


# ------------------------------------------------------------------ arm identities (needs the sim)

def _sim_ready() -> bool:
    repo = Path(__file__).resolve().parents[2]
    return (repo / "simulator" / "out" / "s2_null_effect" / "cohort_blocks.parquet").is_file()


@pytest.mark.skipif(not _sim_ready(), reason="simulator outputs not generated")
def test_arm_identities() -> None:
    """Arm 1 == the frozen `none` cell; arm 2 == the `benjamini_hochberg` cell; 6b == arm 5."""
    from crp_engine.studies import run_study

    for st in run_study():
        cells = {c.regime: c for c in st.cells}
        arms = {(a.arm, a.param): a for a in st.arms}

        none_cell, none_arm = cells["none"], arms[("none", "-")]
        assert (none_arm.n_paid, none_arm.waste_ppm, none_arm.power_ppm,
                none_arm.deployed_ppm, none_arm.max_share_ppm, none_arm.scaled_to_budget) == (
            none_cell.n_paid, none_cell.waste_ppm, none_cell.power_ppm,
            none_cell.deployed_ppm, none_cell.max_share_ppm, none_cell.scaled_to_budget)

        bh_cell, bh_arm = cells["benjamini_hochberg"], arms[("bh", "-")]
        assert (bh_arm.n_paid, bh_arm.waste_ppm, bh_arm.power_ppm, bh_arm.deployed_ppm,
                bh_arm.max_share_ppm, bh_arm.scaled_to_budget) == (
            bh_cell.n_paid, bh_cell.waste_ppm, bh_cell.power_ppm, bh_cell.deployed_ppm,
            bh_cell.max_share_ppm, bh_cell.scaled_to_budget)

        # 6b (cap as a recompiled saturating manifest) reproduces arm 5 (post-hoc cap) to within
        # the documented 1-ppm downward rounding at non-integral crossings, and exactly elsewhere.
        for ppm in CAP_GRID_PPM:
            cap, sat = arms[("cap", format_cap(ppm))], arms[("cr_cap", format_cap(ppm))]
            assert cap.n_paid == sat.n_paid
            assert 0 <= cap.deployed_ppm - sat.deployed_ppm <= 1
            assert 0 <= cap.waste_ppm - sat.waste_ppm <= 1
            assert 0 <= cap.max_share_ppm - sat.max_share_ppm <= 1


@pytest.mark.skipif(not _sim_ready(), reason="simulator outputs not generated")
def test_floor_and_bh_are_redundant_on_the_null_scenario() -> None:
    """The measured refutation/confirmation of the architect's derived claim (study item 4).

    ``s2_null_effect`` has exactly two payers; every floor strictly between their conservative
    effects removes the smaller one — which is the same cohort BH removes. So BH, floor-only and
    BH+floor all land on the SAME waste. Recorded as a test so the redundancy cannot be quietly
    lost when the grid or the seed changes.
    """
    from crp_engine.studies import run_study

    s2 = {s.scenario: s for s in run_study()}["s2_null_effect"]
    assert len(s2.paid_detail) == 2
    big, small = s2.paid_detail
    assert small.conservative_s < big.conservative_s
    arms = {(a.arm, a.param): a for a in s2.arms}
    bh = arms[("bh", "-")]
    for f in FLOOR_GRID_S:
        if small.conservative_s < f <= big.conservative_s:
            assert arms[("floor", format_floor(f))].waste_ppm == bh.waste_ppm
            assert arms[("bh_floor", format_floor(f))].waste_ppm == bh.waste_ppm
            assert arms[("floor", format_floor(f))].max_share_ppm == bh.max_share_ppm


@pytest.mark.skipif(not _sim_ready(), reason="simulator outputs not generated")
def test_proportional_recalibration_cannot_change_the_waste_to_legit_ratio() -> None:
    """A pure rescale is a ``value_scale`` change: it moves exposure, never targeting.

    Both waste and legitimate spend scale by the same rational, so their ratio is invariant up to
    integer rounding. Asserted on ``s2`` (all spend is waste) against ``s1`` (all spend is legit).
    """
    from crp_engine.studies import run_study

    st = {s.scenario: s for s in run_study()}
    base_w = next(a for a in st["s2_null_effect"].arms if a.arm == "none").waste_ppm
    base_l = next(a for a in st["s1_strong_signal"].arms if a.arm == "none").legit_ppm
    base = base_w / base_l
    for num, den in CURVE_SCALE_GRID:
        p = format_scale(num, den)
        w = next(a for a in st["s2_null_effect"].arms if a.arm == "cr" and a.param == p).waste_ppm
        l = next(
            a for a in st["s1_strong_signal"].arms if a.arm == "cr" and a.param == p
        ).legit_ppm
        assert abs(w / l - base) < 1e-3
