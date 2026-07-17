"""Domain-separated binary Merkle tree reference implementation.

Proposed rules (subject to protocol-architect ratification):

  * Hash function: SHA-256.
  * Domain separation by construction:
      leaf_hash(i)  = SHA-256( 0x00 || DOMAIN_TAG || canonical_leaf_bytes )
      node_hash     = SHA-256( 0x01 || left_hash || right_hash )
    The 0x00 / 0x01 prefixes make it impossible for a leaf preimage to be
    reinterpreted as an internal node (second-preimage protection).
  * DOMAIN_TAG is a distinct ASCII byte string per tree type
    (participant / assignment / evidence / reward) so a leaf from one tree can
    never be replayed into another.
  * Leaf ORDER is not the caller's insertion order. Each tree type defines a
    canonical sort key derived from the data; callers sort before building.
  * ODD level handling: the unpaired trailing node is PROMOTED unchanged to the
    next level (it is NOT duplicated). Duplicating the last node
    (Bitcoin-style) enables CVE-2012-2459-type root collisions; promotion
    avoids that class of ambiguity.
  * EMPTY tree root: 32 zero bytes.
"""

from __future__ import annotations

from typing import List

from canonical import sha256

__all__ = [
    "LEAF_PREFIX",
    "NODE_PREFIX",
    "EMPTY_ROOT",
    "DOMAIN_PARTICIPANT",
    "DOMAIN_ASSIGNMENT",
    "DOMAIN_EVIDENCE",
    "DOMAIN_REWARD",
    "leaf_hash",
    "node_hash",
    "merkle_root",
]

LEAF_PREFIX = b"\x00"
NODE_PREFIX = b"\x01"
EMPTY_ROOT = b"\x00" * 32

# Per-tree domain tags (ASCII). Distinct by construction.
DOMAIN_PARTICIPANT = b"CRP:participant:v1"
DOMAIN_ASSIGNMENT = b"CRP:assignment:v1"
DOMAIN_EVIDENCE = b"CRP:evidence:v1"
DOMAIN_REWARD = b"CRP:reward:v1"


def leaf_hash(domain: bytes, canonical_bytes: bytes) -> bytes:
    return sha256(LEAF_PREFIX + domain + canonical_bytes)


def node_hash(left: bytes, right: bytes) -> bytes:
    return sha256(NODE_PREFIX + left + right)


def merkle_root(leaf_canonical_list: List[bytes], domain: bytes) -> bytes:
    """Build the Merkle root from an ORDERED list of canonical leaf byte strings.

    The caller is responsible for having already placed the leaves in the
    tree's canonical order. This function does not reorder.
    """
    if not leaf_canonical_list:
        return EMPTY_ROOT
    level = [leaf_hash(domain, lb) for lb in leaf_canonical_list]
    while len(level) > 1:
        nxt: List[bytes] = []
        for i in range(0, len(level), 2):
            if i + 1 < len(level):
                nxt.append(node_hash(level[i], level[i + 1]))
            else:
                nxt.append(level[i])  # promote unpaired trailing node
        level = nxt
    return level[0]
