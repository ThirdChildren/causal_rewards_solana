"""The reward compiler: cohort value -> device leaves (``specs/reward-policy.md``).

Two stages, both fully frozen before the seed is revealed:

**Stage 1 — cohort valuation.** For each geo-cohort ``c``:

    improvement_c_s  = transform(effect_c_s)                     # positive == better
    margin_c_s       = round_he(critical_value_micro * se_c_s / 1_000_000)
    conservative_c_s = max(0, improvement_c_s - margin_c_s)      # INVARIANT 3
    alloc_c          = reward_curve(conservative_c_s)            # integer piecewise-linear
    budget_c         = alloc_c, scaled down proportionally (floor) if sum(alloc) > B

A cohort that fails ANY frozen minimum-sample threshold, or whose per-cohort effect is not
identified, is forced to ``conservative_c_s = 0``. If fewer than ``min_eligible_cohorts`` cohorts
are eligible the WHOLE distribution is null and the entire budget is recoverable.

**Stage 2 — intra-cohort split.** ``w_i`` from the frozen CRP-WS1 weight formula over anchored
evidence; ``leaf_i(c) = floor(budget_c * w_i / W)``. Floor at every step, so
``sum(leaves) <= sum(budget_c) <= B`` always.

**Leaf set (RATIFIED, `serialization.md` §6.6 v1.1).** Aggregate over cohorts: exactly ONE leaf
per recipient, zero-sum recipients OMITTED, ranked by ``recipient`` (BE32) then ``amount``,
``leaf_index`` = 0-based rank contiguous from 0. Duplicate recipient = hard error. The bytes are
produced by :mod:`crp_engine.reference` — the ratified conformance oracle — never re-implemented
here.

Scale note: `effect_scale` is a *scale exponent* (``"-6"`` -> 1e-6). All Stage-1/Stage-2
arithmetic below is integer arithmetic on already-quantized values; no float touches a committed
number.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from crp_engine import numeric as nm
from crp_engine.estimators import CohortEffect
from crp_engine.manifest import Manifest
from crp_engine.panel import CohortSample, IdentificationMode
from crp_engine.reference import (
    RewardLeaf,
    aggregate_contributions,
    compile_reward_leaves,
    reward_leaf_hash,
    reward_root,
)

__all__ = [
    "ParticipantRow",
    "CohortValuation",
    "Stage1Result",
    "SplitRow",
    "RewardCompilation",
    "improvement_from_effect",
    "stage1_valuation",
    "stage2_split",
    "compile_rewards",
    "DuplicateRecipientError",
]

_PPM = 1_000_000


class DuplicateRecipientError(ValueError):
    """Two leaves share a ``recipient`` — a compiler bug (§6.6: recipient is a unique key)."""


@dataclass(frozen=True)
class ParticipantRow:
    """One participant's anchored-evidence attributes within ONE cohort.

    ``recipient`` is the 32-byte ed25519 signer pubkey that signed the observations — exactly the
    reward ``recipient`` of `serialization.md` §6.6. Attributes are non-negative integers from the
    closed CRP-WS1 vocabulary, computed by the evidence pipeline from signature-verified data.
    """

    cohort_id: str
    recipient: bytes
    attributes: Mapping[str, int]

    def __post_init__(self) -> None:
        if len(self.recipient) != 32:
            raise ValueError("recipient must be 32 bytes, got %d" % len(self.recipient))
        for k, v in self.attributes.items():
            if int(v) < 0:
                raise ValueError("CRP-WS1 attribute %r must be non-negative, got %d" % (k, v))


@dataclass(frozen=True)
class CohortValuation:
    cohort_id: str
    effect_s: int
    se_s: int
    improvement_s: int
    margin_s: int
    conservative_s: int
    min_sample_eligible: bool
    identified: bool
    reasons: tuple[str, ...]
    alloc_base_units: int
    budget_base_units: int


@dataclass(frozen=True)
class Stage1Result:
    cohorts: tuple[CohortValuation, ...]
    n_eligible_cohorts: int
    min_eligible_cohorts: int
    null_distribution: bool
    null_reasons: tuple[str, ...]
    total_alloc_before_cap: int
    total_budget_allocated: int
    budget_base_units: int
    scaled_to_budget: bool


@dataclass(frozen=True)
class SplitRow:
    """Stage-2 per-(cohort, recipient) detail. This is the audit-bundle row, not the on-chain leaf."""

    cohort_id: str
    recipient: bytes
    weight: int
    cohort_weight_total: int
    cohort_budget_base_units: int
    amount_base_units: int


@dataclass(frozen=True)
class RewardCompilation:
    stage1: Stage1Result
    split_rows: tuple[SplitRow, ...]
    leaves: tuple[RewardLeaf, ...]
    reward_root_hex: str
    total_leaf_base_units: int
    dropped_zero_sum_recipients: tuple[bytes, ...]

    @property
    def leaf_count(self) -> int:
        return len(self.leaves)


# --------------------------------------------------------------------------------------
# Stage 1
# --------------------------------------------------------------------------------------

def improvement_from_effect(effect_s: int, manifest: Manifest) -> int:
    """Apply ``positive_improvement_transform`` so that "better" is positive.

    The SE is invariant under the sign flip (``reward-policy.md`` Stage 1 step 2), so only the
    point estimate is transformed. A transform that would pay for a *worse* outcome (identity on
    a ``decrease`` metric, or negation on an ``increase`` metric) is rejected as a manifest bug
    rather than silently paid out.
    """
    t = manifest.reward_policy.transform_type
    direction = manifest.improvement_direction
    if t == "negate_then_clamp":
        if direction != "decrease":
            raise ValueError(
                "negate_then_clamp with improvement_direction=%r would pay for a worse outcome"
                % direction
            )
        return -effect_s
    if t == "identity_clamp":
        if direction != "increase":
            raise ValueError(
                "identity_clamp with improvement_direction=%r would pay for a worse outcome"
                % direction
            )
        return effect_s
    if t == "signed":
        return effect_s if direction == "increase" else -effect_s
    raise ValueError("unknown positive_improvement_transform.type %r" % t)


def stage1_valuation(
    manifest: Manifest,
    effects: Mapping[str, CohortEffect],
    samples: Mapping[str, CohortSample],
    *,
    identification: IdentificationMode = IdentificationMode.WITHIN_COHORT,
) -> Stage1Result:
    """Value every cohort from its conservative causal effect. Deterministic, integer-only."""
    rp = manifest.reward_policy
    plan = manifest.analysis_plan
    scale = rp.effect_scale
    cv_micro = plan.critical_value_micro

    null_reasons: list[str] = []
    design_blocked = not manifest.design.eligible_for_strong_causal_claim
    if design_blocked:
        null_reasons.append(
            "design.eligible_for_strong_causal_claim is false (template=%s): the engine emits a "
            "discovery-only analysis and compiles NO positive payout."
            % manifest.design.template
        )
    if identification is IdentificationMode.NOT_IDENTIFIED:
        null_reasons.append(
            "no per-cohort contrast is identified under this design/assignment pattern"
        )

    valuations: list[CohortValuation] = []
    n_eligible = 0
    for cid in sorted(samples):
        sample = samples[cid]
        eff = effects.get(cid)
        reasons: list[str] = list(sample.reasons)
        identified = bool(eff and eff.identified)
        if not identified:
            reasons.append("per_cohort_effect_not_identified")
        if design_blocked:
            reasons.append("design_not_eligible_for_causal_reward")

        effect_s = nm.quantize(eff.effect, scale) if eff else 0
        se_s = nm.quantize(eff.standard_error, scale) if eff else 0
        if se_s < 0:
            raise ValueError("standard error quantized negative for cohort %r" % cid)

        if sample.eligible:
            n_eligible += 1

        if sample.eligible and identified and not design_blocked:
            improvement_s = improvement_from_effect(effect_s, manifest)
            margin_s = nm.round_half_even_div(cv_micro * se_s, _PPM)
            conservative_s = max(0, improvement_s - margin_s)
        else:
            improvement_s = improvement_from_effect(effect_s, manifest) if eff else 0
            margin_s = nm.round_half_even_div(cv_micro * se_s, _PPM)
            conservative_s = 0  # forced (Invariant 3)

        valuations.append(
            CohortValuation(
                cohort_id=cid,
                effect_s=effect_s,
                se_s=se_s,
                improvement_s=improvement_s,
                margin_s=margin_s,
                conservative_s=conservative_s,
                min_sample_eligible=sample.eligible,
                identified=identified,
                reasons=tuple(reasons),
                alloc_base_units=0,
                budget_base_units=0,
            )
        )

    min_eligible = plan.minimum_sample.min_eligible_cohorts
    if n_eligible < min_eligible:
        null_reasons.append(
            "only %d cohort(s) meet the frozen minimum-sample rule, below min_eligible_cohorts=%d"
            % (n_eligible, min_eligible)
        )
    null = bool(null_reasons)

    if null:
        valuations = [
            CohortValuation(**{**v.__dict__, "conservative_s": 0, "alloc_base_units": 0,
                               "budget_base_units": 0})
            for v in valuations
        ]
        return Stage1Result(
            cohorts=tuple(valuations),
            n_eligible_cohorts=n_eligible,
            min_eligible_cohorts=min_eligible,
            null_distribution=True,
            null_reasons=tuple(null_reasons),
            total_alloc_before_cap=0,
            total_budget_allocated=0,
            budget_base_units=rp.budget_base_units,
            scaled_to_budget=False,
        )

    allocs = [nm.piecewise_linear(v.conservative_s, rp.breakpoints) for v in valuations]
    S = sum(allocs)
    B = rp.budget_base_units
    if S <= B:
        budgets = list(allocs)
        scaled = False
    else:
        if rp.overflow_policy != "proportional_scale_to_budget":
            raise ValueError("unsupported overflow_policy %r" % rp.overflow_policy)
        budgets = [(a * B) // S for a in allocs]  # floor => sum <= B
        scaled = True

    valuations = [
        CohortValuation(**{**v.__dict__, "alloc_base_units": a, "budget_base_units": b})
        for v, a, b in zip(valuations, allocs, budgets)
    ]
    total_budget = sum(budgets)
    if total_budget > B:  # pragma: no cover - guaranteed by floor division
        raise AssertionError("budget guarantee violated: %d > %d" % (total_budget, B))

    return Stage1Result(
        cohorts=tuple(valuations),
        n_eligible_cohorts=n_eligible,
        min_eligible_cohorts=min_eligible,
        null_distribution=False,
        null_reasons=(),
        total_alloc_before_cap=S,
        total_budget_allocated=total_budget,
        budget_base_units=B,
        scaled_to_budget=scaled,
    )


# --------------------------------------------------------------------------------------
# Stage 2
# --------------------------------------------------------------------------------------

def _weight(row: ParticipantRow, terms: Sequence[tuple[int, str]]) -> int:
    """CRP-WS1: ``w_i = sum_k coef_k * attribute_k(i)``. Integer arithmetic, no rounding."""
    total = 0
    for coef, attr in terms:
        if attr not in row.attributes:
            raise ValueError(
                "participant %s in cohort %r is missing CRP-WS1 attribute %r required by the "
                "frozen weight_formula" % (row.recipient.hex(), row.cohort_id, attr)
            )
        total += coef * int(row.attributes[attr])
    return total


def stage2_split(
    manifest: Manifest,
    stage1: Stage1Result,
    participants: Iterable[ParticipantRow],
) -> tuple[SplitRow, ...]:
    """Split each cohort's ``budget_c`` by the frozen quality-weighted rule.

    Iteration order is fully deterministic: cohorts in sorted id order, participants in ascending
    ``recipient`` byte order within a cohort. No dict/set iteration order reaches an output.
    """
    terms = manifest.reward_policy.weight_terms
    budget_by_cohort = {v.cohort_id: v.budget_base_units for v in stage1.cohorts}

    by_cohort: dict[str, list[ParticipantRow]] = {}
    for row in participants:
        by_cohort.setdefault(row.cohort_id, []).append(row)

    out: list[SplitRow] = []
    for cid in sorted(by_cohort):
        rows = sorted(by_cohort[cid], key=lambda r: r.recipient)
        seen: set[bytes] = set()
        for r in rows:
            if r.recipient in seen:
                raise ValueError(
                    "participant table has duplicate recipient %s within cohort %r"
                    % (r.recipient.hex(), cid)
                )
            seen.add(r.recipient)
        budget_c = budget_by_cohort.get(cid, 0)
        weights = [_weight(r, terms) for r in rows]
        W = sum(weights)
        for r, w in zip(rows, weights):
            amount = (budget_c * w) // W if (W > 0 and budget_c > 0) else 0
            out.append(
                SplitRow(
                    cohort_id=cid,
                    recipient=r.recipient,
                    weight=w,
                    cohort_weight_total=W,
                    cohort_budget_base_units=budget_c,
                    amount_base_units=amount,
                )
            )
        if budget_c > 0 and sum(
            (budget_c * w) // W if W > 0 else 0 for w in weights
        ) > budget_c:  # pragma: no cover - guaranteed by floor division
            raise AssertionError("Stage-2 split exceeded cohort budget for %r" % cid)
    return tuple(out)


# --------------------------------------------------------------------------------------
# Leaf set + root (bytes come from the ratified reference)
# --------------------------------------------------------------------------------------

def compile_rewards(
    manifest: Manifest,
    effects: Mapping[str, CohortEffect],
    samples: Mapping[str, CohortSample],
    participants: Iterable[ParticipantRow],
    *,
    identification: IdentificationMode = IdentificationMode.WITHIN_COHORT,
) -> RewardCompilation:
    """Full Stage-1 -> Stage-2 -> aggregate-leaf-set -> ``reward_root`` compilation."""
    s1 = stage1_valuation(manifest, effects, samples, identification=identification)
    rows = stage2_split(manifest, s1, participants)
    return finalize_leaves(s1, rows)


def finalize_leaves(stage1: Stage1Result, split_rows: Sequence[SplitRow]) -> RewardCompilation:
    """Aggregate per recipient, drop zero-sum recipients, rank, and hash the tree.

    Every byte below is produced by ``verifier-cli/reference/reward.py`` (the ratified oracle);
    this function only feeds it the compiler's output and re-raises its guards under a typed
    exception.
    """
    contributions = [(r.recipient, r.amount_base_units) for r in split_rows]
    aggregate = aggregate_contributions(contributions)
    dropped = tuple(sorted(r for r, a in aggregate.items() if a == 0))
    leaves = compile_reward_leaves(aggregate)
    try:
        root = reward_root(leaves)
    except ValueError as exc:
        if "duplicate recipient" in str(exc):
            raise DuplicateRecipientError(str(exc)) from exc
        raise
    total = sum(lf.amount_base_units for lf in leaves)
    if total > stage1.budget_base_units:  # pragma: no cover - guaranteed by floors
        raise AssertionError(
            "budget guarantee violated: leaves sum to %d > B=%d" % (total, stage1.budget_base_units)
        )
    return RewardCompilation(
        stage1=stage1,
        split_rows=tuple(split_rows),
        leaves=tuple(leaves),
        reward_root_hex=root.hex(),
        total_leaf_base_units=total,
        dropped_zero_sum_recipients=dropped,
    )


def leaf_hash_hex(leaf: RewardLeaf) -> str:
    """Convenience: the §6.6 leaf hash of one compiled leaf, as lowercase hex."""
    return reward_leaf_hash(leaf.recipient, leaf.amount_base_units, leaf.leaf_index).hex()
