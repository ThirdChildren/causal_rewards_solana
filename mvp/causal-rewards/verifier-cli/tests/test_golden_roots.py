"""Reproduce every shared golden root through the SAME reference oracle the CLI uses.

A bundle carries one reward root and (here) one epoch, so the full golden set of evidence
sub-trees and reward trees is reproduced here directly from the ratified ``test-vectors/``
inputs — proving the verifier's oracle re-derives each one, not just echoes it.
"""

from __future__ import annotations

import json
from pathlib import Path

from crp_verifier import _ref

REPO = Path(__file__).resolve().parents[2]
VECTORS = REPO / "test-vectors"


def _v(rel: str) -> dict:
    return json.loads((VECTORS / rel).read_bytes().decode("utf-8"))


def test_evidence_epoch_root_evidence_01() -> None:
    v = _v("evidence/evidence-01-epoch-multibatch.json")
    root, _ = _ref.evidence.epoch_tree(v["inputs"]["batches"])
    assert root.hex() == v["evidence_epoch_root_hex"] == \
        "a13e1cdc8702252b89ab08b6943ae82bc65325c2bbce119211a270abc87deeb2"


def test_signer_set_root_evidence_02() -> None:
    v = _v("evidence/evidence-02-signer-set-multisigner.json")
    root, _ = _ref.evidence.signer_subtree(v["inputs"]["signer_pubkeys_base58"])
    assert root.hex() == v["signer_set_root_hex"] == \
        "e45697c86d48d63b8c25a975224344060a4b5cf72bd7d00b3364b6247e5fd52e"


def test_observations_root_evidence_03() -> None:
    v = _v("evidence/evidence-03-observation-set.json")
    root, _ = _ref.evidence.observation_subtree(v["inputs"]["payload_commitment_hexes"])
    assert root.hex() == v["observations_root_hex"] == \
        "1010891bf501f89b96db447a295d0820c20ad694afdcff4cf5c0c2e368ebaf56"


def _reward_root(v: dict) -> str:
    leaves = [
        _ref.reward.RewardLeaf(bytes.fromhex(l["recipient_hex"]), int(l["amount_base_units"]),
                               int(l["leaf_index"]))
        for l in v["leaves"]
    ]
    return _ref.reward.reward_root(leaves).hex()


def test_reward_root_reward_01() -> None:
    v = _v("reward/reward-01-multi-recipient-ordering.json")
    assert _reward_root(v) == v["reward_root_hex"] == \
        "a9c35cf41603d593c123e962f41fc47a2d750cf1e536b177f2454ace647fc171"


def test_reward_root_reward_02() -> None:
    v = _v("reward/reward-02-zero-sum-dropped.json")
    assert _reward_root(v) == v["reward_root_hex"] == \
        "ea9431826b81982577d70ea8ac6159aa8b600a77889c45c84b2ff5afc8ae0ffc"


def test_reward_root_reward_03() -> None:
    v = _v("reward/reward-03-single-recipient.json")
    assert _reward_root(v) == v["reward_root_hex"] == \
        "b882c8992309c1269d9e9d6b887faeb2c2361ea112d5c495fe00c520d8655ced"
