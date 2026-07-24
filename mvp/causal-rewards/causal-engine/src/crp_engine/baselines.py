"""The four reward baselines, compared under ONE fixed budget (``docs/benchmark-plan.md``).

Every allocator receives the same ``budget_base_units`` and the same cohort table, and returns
per-cohort base-unit amounts. Only the *cohort valuation* differs; Stage 2 (the frozen
quality-weighted intra-cohort split) is identical for all four, so the comparison isolates the
question the protocol actually asks: **does conditioning payment on measured additionality
allocate the same budget better than activity / quality / scarcity heuristics?**

* ``activity``   — proportional to accepted observations. What most DePIN networks do today.
* ``quality``    — proportional to quality-adjusted observations.
* ``scarcity``   — proportional to a redundancy/scarcity score (pays for coverage gaps).
* ``causal``     — the frozen Stage-1 conservative valuation (``reward_compiler.stage1_valuation``).

The causal allocator is the only one that can return LESS than the budget: a network with no
measurable additionality pays nothing and the budget is recoverable. That asymmetry is the point,
and it means "causal wins" is not the success criterion — a scenario where causal underperforms a
baseline is a valid, publishable result (CLAUDE.md invariant 8).

Allocation here is integer, floor-based and deterministic (largest-remainder is deliberately NOT
used: it would need a tie-break rule that is not frozen anywhere).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

__all__ = ["BASELINES", "proportional_allocation", "allocate_baseline"]

BASELINES: tuple[str, ...] = ("activity", "quality", "scarcity", "causal")

_KEY = {
    "activity": "accepted_observations",
    "quality": "quality_adjusted_observations",
    "scarcity": "redundancy_score_micro",
}


def proportional_allocation(
    scores: Mapping[str, int], budget_base_units: int
) -> dict[str, int]:
    """``floor(budget * score_c / sum(score))`` in sorted cohort order. Never exceeds the budget."""
    total = sum(max(0, int(v)) for v in scores.values())
    if total <= 0 or budget_base_units <= 0:
        return {cid: 0 for cid in sorted(scores)}
    return {
        cid: (budget_base_units * max(0, int(scores[cid]))) // total for cid in sorted(scores)
    }


@dataclass(frozen=True)
class CohortFeatures:
    """Per-cohort heuristic inputs, summed from anchored evidence."""

    cohort_id: str
    accepted_observations: int
    quality_adjusted_observations: int
    redundancy_score_micro: int


def allocate_baseline(
    name: str,
    features: Sequence[CohortFeatures],
    budget_base_units: int,
    *,
    causal_budgets: Mapping[str, int] | None = None,
) -> dict[str, int]:
    """Allocate the fixed budget under one baseline. ``causal`` just echoes Stage-1's output."""
    if name == "causal":
        if causal_budgets is None:
            raise ValueError("the causal baseline requires the Stage-1 per-cohort budgets")
        return {f.cohort_id: int(causal_budgets.get(f.cohort_id, 0)) for f in
                sorted(features, key=lambda f: f.cohort_id)}
    if name not in _KEY:
        raise ValueError("unknown baseline %r (expected one of %s)" % (name, list(BASELINES)))
    attr = _KEY[name]
    return proportional_allocation(
        {f.cohort_id: int(getattr(f, attr)) for f in features}, budget_base_units
    )
