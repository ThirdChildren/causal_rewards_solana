"""Reward leaf + reward-root reference implementation (serialization.md §6.6, RATIFIED v1.1).

The reward tree is a §6.1-shaped Merkle tree over one leaf per reward entry produced by the
Stage-2 reward compiler (reward-policy.md), under the ratified **aggregate-one-leaf-per-recipient**
shape. Unlike CJSON artifacts, a reward leaf is a FIXED-WIDTH RAW-BYTE structure (§2/§3 do not
apply); the §6.1 node formulas do.

Leaf preimage (fixed width, 48 bytes of content):

    recipient          : 32 raw bytes  — recipient ed25519 pubkey (native 32-byte form)
    amount_base_units  :  8 bytes, u64 BIG-ENDIAN — mint-native base units (money, scale 1)
    leaf_index         :  8 bytes, u64 BIG-ENDIAN — 0-based tree position / nullifier key

    reward_leaf_content = recipient || amount_be || leaf_index_be                # 48 bytes
    leaf_hash           = SHA-256( 0x00 || "CRP:reward:v1" || reward_leaf_content )

Leaf-set shape (RESIDUAL A, §6.6): aggregate over cohorts — for each distinct recipient R one
leaf (R, amount = Σ_c leaf_i(c)); **recipients whose aggregate sum is 0 are OMITTED**. Ranking
(→ leaf_index): ascending by `recipient` (unsigned big-endian 32-byte compare — the unique
primary key), then ascending by `amount_base_units` (never decisive; retained for defensive
consistency). Because `recipient` is unique after aggregation, two leaves sharing a `recipient`
is a HARD ERROR (a compiler bug). Leaves are placed by leaf_index ascending, contiguous from 0.
The empty reward tree (N = 0) has root = 32 zero bytes (§6.4).

Pure functions of the committed inputs: no wall-clock, no RNG, no float.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from canonical import sha256
from merkle import DOMAIN_REWARD, LEAF_PREFIX, merkle_root

__all__ = [
    "RECIPIENT_LEN",
    "U64_MAX",
    "reward_leaf_content",
    "reward_leaf_hash",
    "RewardLeaf",
    "aggregate_contributions",
    "compile_reward_leaves",
    "reward_root",
]

RECIPIENT_LEN = 32
U64_MAX = (1 << 64) - 1


def _check_u64(name: str, v: int) -> None:
    if not (0 <= v <= U64_MAX):
        raise ValueError("%s out of u64 range: %d" % (name, v))


def reward_leaf_content(recipient: bytes, amount_base_units: int, leaf_index: int) -> bytes:
    """The 48-byte fixed-width leaf content: recipient(32) || amount(u64 BE) || leaf_index(u64 BE)."""
    if len(recipient) != RECIPIENT_LEN:
        raise ValueError(
            "recipient must be exactly %d bytes, got %d" % (RECIPIENT_LEN, len(recipient))
        )
    _check_u64("amount_base_units", amount_base_units)
    _check_u64("leaf_index", leaf_index)
    return (
        recipient
        + amount_base_units.to_bytes(8, "big")
        + leaf_index.to_bytes(8, "big")
    )


def reward_leaf_hash(recipient: bytes, amount_base_units: int, leaf_index: int) -> bytes:
    content = reward_leaf_content(recipient, amount_base_units, leaf_index)
    return sha256(LEAF_PREFIX + DOMAIN_REWARD + content)


@dataclass(frozen=True)
class RewardLeaf:
    recipient: bytes
    amount_base_units: int
    leaf_index: int


def aggregate_contributions(
    contributions: Sequence[Tuple[bytes, int]]
) -> Dict[bytes, int]:
    """Sum per-(recipient, cohort) Stage-2 amounts into a per-recipient aggregate map.

    `contributions` is a flat list of (recipient_bytes, amount) pairs — one entry per
    (recipient, cohort) in which the recipient earned a Stage-2 amount. Integer addition only
    (no rounding, §2.4). Zero-sum recipients are NOT dropped here; that happens in
    compile_reward_leaves (the leaf-set shaping step).
    """
    agg: Dict[bytes, int] = {}
    for recipient, amount in contributions:
        if len(recipient) != RECIPIENT_LEN:
            raise ValueError(
                "recipient must be exactly %d bytes, got %d" % (RECIPIENT_LEN, len(recipient))
            )
        if amount < 0:
            raise ValueError("Stage-2 amounts are non-negative; got %d" % amount)
        agg[recipient] = agg.get(recipient, 0) + amount
    return agg


def compile_reward_leaves(aggregate: Dict[bytes, int]) -> List[RewardLeaf]:
    """Apply the §6.6 leaf-set shape to a per-recipient aggregate map → ordered, indexed leaves.

    Steps: (1) OMIT any recipient whose aggregate sum is 0 (unclaimable value, wasted nullifier);
    (2) rank the remaining recipients ascending by `recipient` (BE32, unique primary key) then
    `amount_base_units`; (3) assign leaf_index = 0-based rank. `recipient` is unique after
    aggregation, so this is a total order with no tie-break residual.
    """
    nonzero = [(r, a) for r, a in aggregate.items() if a != 0]
    ranked = sorted(nonzero, key=lambda ra: (ra[0], ra[1]))
    return [RewardLeaf(r, a, i) for i, (r, a) in enumerate(ranked)]


def reward_root(leaves: Sequence[RewardLeaf]) -> bytes:
    """Reward Merkle root over an ordered leaf set. Rejects malformed compiler output.

    Enforces the §6.6 normative guards on the FINAL leaf set (defensive; a conforming
    compile_reward_leaves output already satisfies them):
      * duplicate `recipient` → HARD ERROR (compiler bug; recipient is a unique key),
      * leaf_index values MUST be exactly 0 … N-1 (no gaps, no duplicates),
      * leaves placed by leaf_index ascending, contiguous from 0.
    Empty leaf set → 32 zero bytes (§6.4, via merkle_root).
    """
    seen_recipient = set()
    by_index: Dict[int, RewardLeaf] = {}
    for lf in leaves:
        if lf.recipient in seen_recipient:
            raise ValueError(
                "duplicate recipient in reward leaf set (compiler bug): %s"
                % lf.recipient.hex()
            )
        seen_recipient.add(lf.recipient)
        if lf.leaf_index in by_index:
            raise ValueError("duplicate leaf_index in reward tree: %d" % lf.leaf_index)
        by_index[lf.leaf_index] = lf

    n = len(leaves)
    expected = set(range(n))
    if set(by_index.keys()) != expected:
        raise ValueError(
            "leaf_index set must be exactly 0..N-1 (no gaps); got %s for N=%d"
            % (sorted(by_index.keys()), n)
        )

    ordered_contents = [
        reward_leaf_content(
            by_index[i].recipient, by_index[i].amount_base_units, i
        )
        for i in range(n)
    ]
    return merkle_root(ordered_contents, DOMAIN_REWARD)
