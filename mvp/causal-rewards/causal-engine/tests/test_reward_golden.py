"""HARD ACCEPTANCE GATE — the ratified reward vectors in ``test-vectors/reward/``.

If any assertion in this file fails, the engine does NOT ship. A golden root is never adjusted
to match the engine; the engine is adjusted to match the golden root.

Covers: multi-recipient ordering + Σ over cohorts (reward-01), zero-sum omission (reward-02),
single-recipient base case (reward-03), the duplicate-recipient HARD ERROR (reward-04), and the
empty tree (reward-05).
"""

from __future__ import annotations

import json

import pytest

from crp_engine.reference import RewardLeaf, reward_leaf_content, reward_leaf_hash, reward_root
from crp_engine.reward_compiler import (
    DuplicateRecipientError,
    SplitRow,
    Stage1Result,
    finalize_leaves,
)
from tests.conftest import REWARD_VECTORS

_EMPTY_STAGE1 = Stage1Result(
    cohorts=(),
    n_eligible_cohorts=0,
    min_eligible_cohorts=0,
    null_distribution=False,
    null_reasons=(),
    total_alloc_before_cap=0,
    total_budget_allocated=0,
    budget_base_units=(1 << 64) - 1,
    scaled_to_budget=False,
)


def _load(name: str) -> dict:
    return json.loads((REWARD_VECTORS / (name + ".json")).read_text(encoding="utf-8"))


def _index() -> dict:
    return json.loads((REWARD_VECTORS / "index.json").read_text(encoding="utf-8"))


def _rows(vec: dict) -> list[SplitRow]:
    return [
        SplitRow(
            cohort_id=c["cohort_id"],
            recipient=bytes.fromhex(c["recipient_hex"]),
            weight=1,
            cohort_weight_total=1,
            cohort_budget_base_units=int(c["amount_base_units"]),
            amount_base_units=int(c["amount_base_units"]),
        )
        for c in vec["inputs"]["contributions"]
    ]


POSITIVE = [e["name"] for e in _index()["vectors"] if e["kind"] == "reward_positive"]
EMPTY = [e["name"] for e in _index()["vectors"] if e["kind"] == "reward_empty"]


@pytest.mark.parametrize("name", POSITIVE + EMPTY)
def test_reward_root_matches_golden(name: str) -> None:
    vec = _load(name)
    entry = next(e for e in _index()["vectors"] if e["name"] == name)
    got = finalize_leaves(_EMPTY_STAGE1, _rows(vec))
    assert got.reward_root_hex == entry["reward_root_hex"], (
        "GOLDEN REWARD ROOT MISMATCH for %s: engine produced %s, ratified vector says %s"
        % (name, got.reward_root_hex, entry["reward_root_hex"])
    )
    assert got.reward_root_hex == vec["reward_root_hex"]


@pytest.mark.parametrize("name", POSITIVE)
def test_leaf_indices_amounts_and_hashes_match_golden(name: str) -> None:
    vec = _load(name)
    got = finalize_leaves(_EMPTY_STAGE1, _rows(vec))
    assert len(got.leaves) == len(vec["leaves"])
    for leaf, want in zip(got.leaves, vec["leaves"]):
        assert leaf.leaf_index == int(want["leaf_index"])
        assert leaf.recipient.hex() == want["recipient_hex"]
        assert leaf.amount_base_units == int(want["amount_base_units"])
        assert (
            reward_leaf_content(
                leaf.recipient, leaf.amount_base_units, leaf.leaf_index
            ).hex()
            == want["leaf_content_hex"]
        )
        assert (
            reward_leaf_hash(
                leaf.recipient, leaf.amount_base_units, leaf.leaf_index
            ).hex()
            == want["leaf_hash_hex"]
        )


def test_zero_sum_recipients_are_omitted() -> None:
    vec = _load("reward-02-zero-sum-dropped")
    got = finalize_leaves(_EMPTY_STAGE1, _rows(vec))
    dropped = {r.hex() for r in got.dropped_zero_sum_recipients}
    assert dropped == set(vec["dropped_zero_sum_recipients_hex"])
    # A dropped recipient must not consume a leaf_index, even when it sorts BETWEEN survivors.
    assert [lf.leaf_index for lf in got.leaves] == list(range(len(got.leaves)))


def test_aggregation_sums_across_cohorts() -> None:
    vec = _load("reward-01-multi-recipient-ordering")
    got = finalize_leaves(_EMPTY_STAGE1, _rows(vec))
    by_recipient = {lf.recipient.hex(): lf.amount_base_units for lf in got.leaves}
    assert by_recipient == {
        k: int(v) for k, v in vec["aggregate_recipient_amount_map"].items() if int(v) != 0
    }


def test_duplicate_recipient_is_a_hard_error() -> None:
    """reward-04: two leaves sharing a recipient can only be a compiler bug (§6.6)."""
    vec = _load("reward-04-duplicate-recipient-error")
    leaves = [
        RewardLeaf(
            bytes.fromhex(lf["recipient_hex"]),
            int(lf["amount_base_units"]),
            int(lf["leaf_index"]),
        )
        for lf in vec["inputs"]["malformed_leaf_set"]
    ]
    with pytest.raises(ValueError, match="duplicate recipient"):
        reward_root(leaves)


def test_compiler_never_emits_a_duplicate_recipient() -> None:
    """The aggregate shape makes duplicates structurally impossible on the compiler path."""
    rows = [
        SplitRow("c1", b"\x11" * 32, 1, 1, 10, 10),
        SplitRow("c2", b"\x11" * 32, 1, 1, 20, 20),
        SplitRow("c3", b"\x11" * 32, 1, 1, 30, 30),
    ]
    got = finalize_leaves(_EMPTY_STAGE1, rows)
    assert len(got.leaves) == 1
    assert got.leaves[0].amount_base_units == 60


def test_empty_leaf_set_root_is_32_zero_bytes() -> None:
    got = finalize_leaves(_EMPTY_STAGE1, [])
    assert got.reward_root_hex == "00" * 32
    assert got.leaf_count == 0


def test_duplicate_recipient_error_type_is_typed() -> None:
    """The compiler re-raises the reference guard as a typed error the SDK can catch."""
    from crp_engine.reward_compiler import finalize_leaves as fl

    class _Bad(list):
        pass

    leaves = [
        RewardLeaf(b"\x22" * 32, 1, 0),
        RewardLeaf(b"\x22" * 32, 2, 1),
    ]
    with pytest.raises(ValueError, match="duplicate recipient"):
        reward_root(leaves)
    assert issubclass(DuplicateRecipientError, ValueError)
