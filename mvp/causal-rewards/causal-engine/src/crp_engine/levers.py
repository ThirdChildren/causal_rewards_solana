"""Economic and structural spend levers, as a deterministic STUDY-ONLY layer.

``crp_engine.multiplicity`` explores the *statistical* lever (which cohorts pass the test).
This module explores the two non-statistical levers that act on the *spend* itself:

* **conservative-effect FLOOR** (economic gate) — a cohort whose conservative effect is below
  ``floor_s`` deploys no budget at all, however significant it is. Because
  ``piecewise_linear(0, ...) == 0`` for the frozen curve, a floor is exactly representable through
  the existing ``stage1_valuation(selected_cohorts=...)`` hook: a floored-out cohort is forced to
  ``conservative_s = 0`` and therefore ``alloc = 0``. No compiler change, and the floor arms run
  through the real Stage-1/Stage-2/leaf path.
* **per-cohort CAP** (structural gate) — no single cohort may draw more than ``cap_ppm`` parts per
  million of the fixed budget ``B``. The cap is applied to the Stage-1 allocation *before* the
  frozen overflow rule; the clipped excess is NOT redistributed, it is recovered, which is the
  only behavior consistent with the absolute-scale valuation
  (``cohort_reward_pool = value_scale * conservative_effect``, CLAUDE.md).

Both levers change NO frozen default. They are measured against the committed simulator artifacts
so the architect can rule on ``docs/multiplicity-study.md``'s open question.

Determinism (CLAUDE.md invariant 2). Every function here is integer-only and a pure function of
already-quantized Stage-1 output: no float, no RNG, no wall-clock, no dict/set iteration reaching
an output (all outputs are keyed or sorted by ``cohort_id``).
"""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

__all__ = [
    "FLOOR_GRID_S",
    "CAP_GRID_PPM",
    "CURVE_SCALE_GRID",
    "CURVE_REFERENCE_X",
    "PPM",
    "equal_share_scale",
    "floor_selected",
    "cap_base_units",
    "capped_budgets",
    "capped_overflowed",
    "rescale_curve",
    "saturate_curve",
    "format_floor",
    "format_cap",
    "format_scale",
]

PPM = 1_000_000

#: Conservative-effect floors swept by the study, in the manifest's ``effect_scale`` micro units
#: (``-6``). 30_000 / 50_000 are the true effects of the weak-but-real scenarios ``s3_low_power``
#: (0.030) and ``s6_demand_shift`` (0.050); 100_000 is the reward curve's first non-zero
#: breakpoint (0.100 -> 20% of B); 150_000 sits just above the ``s2_null_effect`` false
#: positive's conservative effect (0.139576) and is therefore the smallest grid point that
#: zeroes null waste on the committed draw.
FLOOR_GRID_S: tuple[int, ...] = (10_000, 30_000, 50_000, 100_000, 150_000)

#: Per-cohort caps swept by the study, as parts per million of the fixed budget ``B``.
#: 1/m for the candidate families here (m = 4..22) lies between 45_000 and 250_000 ppm, so the
#: grid brackets the "equal share of the family" reference point.
CAP_GRID_PPM: tuple[int, ...] = (250_000, 100_000, 50_000, 25_000)

#: Proportional recalibrations of the benchmark reward curve, as exact rationals ``(num, den)``.
#:
#: **How these were chosen (not tuned to an outcome).** The absolute-scale rule
#: ``alloc_c = reward_curve(conservative_c)`` is only well posed once the curve is calibrated to the
#: cohort count: the natural calibration is "a network in which EVERY declared cohort delivers the
#: reference effect exactly exhausts ``B``", i.e.
#:
#:     N * curve(x_ref) = B          =>   scale = B / (N * curve_0(x_ref))
#:
#: with ``x_ref`` the curve's own first paying breakpoint (``0.100000`` — the level the curve's
#: author designated as "worth paying") and ``N`` the FROZEN declared ``cohort_count``. The example
#: curve has ``curve_0(x_ref) = B/5``, so the equal-share scale is exactly ``5/N``: ``1/12`` for the
#: 60-cohort scenarios and ``1/4`` for the 20-cohort ``s3_low_power``. Both are on the grid, together
#: with the mild ``1/2`` so the sweep brackets the calibrated point from above.
#:
#: Every input to this rule is frozen pre-analysis (``cohort_count`` and the curve itself), so
#: recalibration is a legitimate pre-registration choice, not a post-hoc fit.
CURVE_SCALE_GRID: tuple[tuple[int, int], ...] = ((1, 2), (1, 4), (1, 12))

#: The reference breakpoint of the calibration rule above, in ``effect_scale`` (-6) units.
CURVE_REFERENCE_X: int = 100_000


def floor_selected(
    conservative_by_cohort: Mapping[str, int],
    floor_s: int,
    *,
    base: Iterable[str] | None = None,
) -> frozenset[str]:
    """Cohorts whose conservative effect clears ``floor_s``, intersected with ``base``.

    ``conservative_by_cohort`` maps candidate cohort id -> its frozen ``conservative_s`` (the
    integer the shipped compiler already produced). ``base`` is an optional prior selection (e.g.
    the BH survivors) so ``BH + floor`` is a plain set intersection: the two gates are independent
    because a cohort's ``conservative_s`` does not depend on which other cohorts were selected.

    ``floor_s <= 0`` reproduces the no-floor behavior exactly (a zero conservative effect already
    allocates zero under the monotone curve through the origin).
    """
    if floor_s < 0:
        raise ValueError("floor_s must be non-negative, got %d" % floor_s)
    keep = {cid for cid, c in conservative_by_cohort.items() if c >= floor_s and c > 0}
    if base is not None:
        keep &= set(base)
    return frozenset(keep)


def cap_base_units(budget_base_units: int, cap_ppm: int) -> int:
    """The per-cohort ceiling in base units: ``floor(cap_ppm * B / 1e6)``. Integer-only."""
    if cap_ppm < 0:
        raise ValueError("cap_ppm must be non-negative, got %d" % cap_ppm)
    if budget_base_units < 0:
        raise ValueError("budget must be non-negative, got %d" % budget_base_units)
    return (cap_ppm * budget_base_units) // PPM


def capped_budgets(
    allocs: Sequence[tuple[str, int]],
    budget_base_units: int,
    cap_ppm: int,
) -> dict[str, int]:
    """Apply the per-cohort cap, then the frozen ``proportional_scale_to_budget`` overflow rule.

    ``allocs`` is ``(cohort_id, alloc_base_units)`` — Stage-1 allocations BEFORE the overflow rule
    (``CohortValuation.alloc_base_units``). Returns ``cohort_id -> budget_base_units``.

    Order of operations mirrors the shipped compiler with one extra clip in front:

        a'_c = min(a_c, floor(cap_ppm * B / 1e6))
        S'   = sum(a'_c)
        b_c  = a'_c                      if S' <= B          (absolute scale, remainder recovered)
        b_c  = floor(a'_c * B / S')      otherwise           (downward-only overflow scaling)

    The clipped excess is never handed to another cohort: under an absolute scale, budget that no
    cohort earned is recovered, not redistributed.
    """
    B = budget_base_units
    cap = cap_base_units(B, cap_ppm)
    clipped = [(cid, min(a, cap)) for cid, a in allocs]
    S = sum(a for _, a in clipped)
    if S <= B:
        return {cid: a for cid, a in clipped}
    return {cid: (a * B) // S for cid, a in clipped}


def capped_overflowed(
    allocs: Sequence[tuple[str, int]],
    budget_base_units: int,
    cap_ppm: int,
) -> bool:
    """Whether the post-cap total still exceeds ``B`` (i.e. the overflow branch fires)."""
    cap = cap_base_units(budget_base_units, cap_ppm)
    return sum(min(a, cap) for _, a in allocs) > budget_base_units


def rescale_curve(
    breakpoints: Sequence[Sequence[int]],
    num: int,
    den: int,
) -> tuple[tuple[int, int], ...]:
    """Multiply every curve OUTPUT by the exact rational ``num/den`` (shape unchanged).

    Rounding is half-to-even on the exact integer ratio, matching ``numeric.round_half_even_div``,
    so the recalibrated curve is as deterministic as the frozen one. Monotonicity is preserved
    because ``num/den > 0`` and the map is applied pointwise to a non-decreasing sequence.

    A proportional rescale is *exactly* a change of ``value_scale``: in the ``S <= B`` branch every
    allocation, and therefore both waste and legitimate spend, scale by the same factor. It cannot
    change the RATIO of the two — see the study's curve-recalibration arm.
    """
    if num <= 0 or den <= 0:
        raise ValueError("rescale requires num > 0 and den > 0, got %d/%d" % (num, den))
    out: list[tuple[int, int]] = []
    for pair in breakpoints:
        x, y = int(pair[0]), int(pair[1])
        q, r = divmod(y * num, den)
        if 2 * r > den or (2 * r == den and q % 2 == 1):
            q += 1
        out.append((x, q))
    return tuple(out)


def saturate_curve(
    breakpoints: Sequence[Sequence[int]],
    ceiling_base_units: int,
) -> tuple[tuple[int, int], ...]:
    """The per-cohort cap expressed *inside the reward curve*: ``min(curve(x), ceiling)``.

    **This is the load-bearing function of the study.** If a saturating curve reproduces the
    post-hoc cap exactly, then a per-cohort cap needs NO new frozen manifest field and NO schema
    change — it is a different ``reward_curve`` fixture, and ``reward_curve`` is already frozen.

    Naively clipping the breakpoint *outputs* does NOT do this: it also flattens the slope of every
    sub-ceiling segment, so cohorts below the cap get paid less than the cap would give them. The
    correct construction INSERTS the crossing point ``x*`` where the original curve first reaches
    the ceiling, then holds flat:

        x* = x0 + ceil((ceiling - y0) * (x1 - x0) / (y1 - y0))     inside the crossing segment

    When ``x*`` is exact (the ratio divides evenly) the result equals ``min(curve(x), ceiling)`` at
    every integer ``x``. When it is not, ``ceil`` is used so the saturating curve pays at most
    ``min(curve(x), ceiling)`` — never more. Under-paying is the conservative direction
    (CLAUDE.md invariant 3), so the approximation can only ever be safe.

    The result is a valid ``piecewise_linear_monotonic`` curve (first breakpoint ``(0, 0)``, ``x``
    strictly increasing, ``y`` non-decreasing), so it validates against the frozen schema unchanged.
    """
    if ceiling_base_units < 0:
        raise ValueError("ceiling must be non-negative, got %d" % ceiling_base_units)
    bps = [(int(x), int(y)) for x, y in breakpoints]
    out: list[tuple[int, int]] = [(bps[0][0], min(bps[0][1], ceiling_base_units))]
    for (x0, y0), (x1, y1) in zip(bps, bps[1:]):
        if y0 >= ceiling_base_units:
            out.append((x1, ceiling_base_units))
            continue
        if y1 <= ceiling_base_units:
            out.append((x1, y1))
            continue
        # The ceiling is crossed strictly inside this segment: insert x*, then hold flat.
        num = (ceiling_base_units - y0) * (x1 - x0)
        den = y1 - y0
        x_star = x0 + -((-num) // den)  # ceil division, integers only
        if x_star > x0:
            out.append((x_star, ceiling_base_units))
        if x1 > max(x_star, x0):
            out.append((x1, ceiling_base_units))
    # Drop duplicate x (can only arise when x* lands exactly on x1).
    dedup: list[tuple[int, int]] = []
    for x, y in out:
        if dedup and dedup[-1][0] == x:
            dedup[-1] = (x, max(dedup[-1][1], y))
        else:
            dedup.append((x, y))
    return tuple(dedup)


def equal_share_scale(
    breakpoints: Sequence[Sequence[int]],
    budget_base_units: int,
    cohort_count: int,
    *,
    reference_x: int = CURVE_REFERENCE_X,
) -> tuple[int, int]:
    """The exact rational ``(num, den)`` making ``cohort_count * curve(reference_x) == B``.

    This is the equal-share calibration described on :data:`CURVE_SCALE_GRID`, returned unreduced
    as ``(B, cohort_count * curve_0(reference_x))``. Pure integer arithmetic on frozen manifest
    fields; no data enters.
    """
    from crp_engine.numeric import piecewise_linear

    if cohort_count <= 0:
        raise ValueError("cohort_count must be positive, got %d" % cohort_count)
    y_ref = piecewise_linear(reference_x, [tuple(int(v) for v in p) for p in breakpoints])
    if y_ref <= 0:
        raise ValueError("curve pays nothing at the reference breakpoint; cannot calibrate")
    return (budget_base_units, cohort_count * y_ref)


def format_floor(floor_s: int, scale_exponent: int = -6) -> str:
    """Human-readable floor, e.g. ``30_000`` at scale ``-6`` -> ``"0.030"``. Deterministic text."""
    if scale_exponent > 0:
        raise ValueError("scale_exponent must be <= 0, got %d" % scale_exponent)
    digits = -scale_exponent
    unit = 10 ** digits
    whole, frac = divmod(abs(floor_s), unit)
    sign = "-" if floor_s < 0 else ""
    return "%s%d.%0*d" % (sign, whole, digits, frac)


def format_cap(cap_ppm: int) -> str:
    """``250_000`` -> ``"25.0%B"``. Exact one-decimal rendering, integer arithmetic only."""
    tenths = cap_ppm // 1_000  # ppm -> tenths of a percent
    return "%d.%d%%B" % divmod(tenths, 10)


def format_scale(num: int, den: int) -> str:
    """``(1, 10)`` -> ``"x1/10"``. Exact, no float."""
    return "x%d/%d" % (num, den)
