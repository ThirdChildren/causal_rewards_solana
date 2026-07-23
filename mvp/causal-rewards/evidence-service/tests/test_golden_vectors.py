"""HARD ACCEPTANCE GATE — reproduce the ratified evidence golden roots byte-for-byte.

If any assertion here fails, the service is non-conformant and the failure is reported
upstream; the golden vector is NEVER adjusted to match the implementation.

The golden batch headers carry PLACEHOLDER signature bytes (``aaaa…``) because they were
authored to pin TREE bytes. The epoch tree is a pure function of ``CJSON(batch)`` and is
independent of whether the signature verifies, so root reproduction is tested directly
against ``roots.evidence_epoch_root`` (the ingestion trust boundary is tested separately in
``test_ingest.py`` with real RFC-8032 signatures).
"""

from __future__ import annotations

import json

import pytest
from fixtures import TEST_VECTORS

from crp_evidence.errors import EvidenceRejected
from crp_evidence.roots import (
    EMPTY_ROOT_HEX,
    evidence_epoch_root,
    observations_root,
    signer_set_root,
)

EV = TEST_VECTORS / "evidence"


def _vector(name: str) -> dict:
    return json.loads((EV / (name + ".json")).read_bytes().decode("utf-8"))


def _index() -> dict:
    return json.loads((EV / "index.json").read_bytes().decode("utf-8"))


def test_evidence_01_epoch_multibatch_root() -> None:
    v = _vector("evidence-01-epoch-multibatch")
    root, records = evidence_epoch_root(v["inputs"]["batches"])
    assert root == v["evidence_epoch_root_hex"]
    assert root == "a13e1cdc8702252b89ab08b6943ae82bc65325c2bbce119211a270abc87deeb2"
    # Leaf order and per-leaf hashes must match the vector exactly, not just the root.
    expected_leaves = v.get("ordered_leaves")
    if expected_leaves:
        assert [r["leaf_hash_hex"] for r in records] == [
            e["leaf_hash_hex"] for e in expected_leaves
        ]


def test_evidence_02_signer_set_root() -> None:
    v = _vector("evidence-02-signer-set-multisigner")
    root, records = signer_set_root(v["inputs"]["signer_pubkeys_base58"])
    assert root == v["signer_set_root_hex"]
    assert root == "e45697c86d48d63b8c25a975224344060a4b5cf72bd7d00b3364b6247e5fd52e"
    assert [r["sort_key_be32_hex"] for r in records] == [
        e["sort_key_be32_hex"] for e in v["ordered_leaves"]
    ]
    assert [r["leaf_hash_hex"] for r in records] == [
        e["leaf_hash_hex"] for e in v["ordered_leaves"]
    ]


def test_evidence_03_observation_set_root() -> None:
    v = _vector("evidence-03-observation-set")
    root, records = observations_root(v["inputs"]["payload_commitment_hexes"])
    assert root == v["observations_root_hex"]
    assert root == "1010891bf501f89b96db447a295d0820c20ad694afdcff4cf5c0c2e368ebaf56"
    assert [r["sort_key_be32_hex"] for r in records] == [
        e["sort_key_be32_hex"] for e in v["ordered_leaves"]
    ]


def test_evidence_04_empty_tree_all_three_trees() -> None:
    v = _vector("evidence-04-empty-tree")
    assert v["empty_root_hex"] == EMPTY_ROOT_HEX
    assert evidence_epoch_root([])[0] == EMPTY_ROOT_HEX
    assert signer_set_root([])[0] == EMPTY_ROOT_HEX
    assert observations_root([])[0] == EMPTY_ROOT_HEX


def test_evidence_05_signer_not_32_bytes_is_a_typed_hard_error() -> None:
    v = _vector("evidence-05-signer-not-32-error")
    pk = v["inputs"]["signer_pubkey_base58"]
    with pytest.raises(EvidenceRejected) as ei:
        signer_set_root([pk])
    assert ei.value.code == v["rejection_code"] == "SIGNER_PUBKEY_NOT_32_BYTES"
    assert ei.value.detail["decoded_length"] == int(v["inputs"]["base58_decoded_length"])


def test_index_declares_exactly_the_vectors_we_replay() -> None:
    names = {e["name"] for e in _index()["vectors"]}
    assert names == {
        "evidence-01-epoch-multibatch",
        "evidence-02-signer-set-multisigner",
        "evidence-03-observation-set",
        "evidence-04-empty-tree",
        "evidence-05-signer-not-32-error",
    }, "a new evidence vector landed; add an explicit replay above"


def test_adversarial_duplicate_evidence_leaf_vector() -> None:
    """adv-03: the same signed batch twice in one epoch is a typed hard error."""
    adv = json.loads(
        (TEST_VECTORS / "adversarial" / "adv-03-replayed-evidence-batch.json")
        .read_bytes()
        .decode("utf-8")
    )
    a, b = adv["inputs"]["batch_a"], adv["inputs"]["batch_b"]
    with pytest.raises(EvidenceRejected) as ei:
        evidence_epoch_root([a, b])
    assert ei.value.code == adv["rejection_code"] == "DUPLICATE_EVIDENCE_LEAF"
    assert ei.value.detail["sort_key_hex"] == adv["expected"]["batch_a_leaf_hash_hex"]
