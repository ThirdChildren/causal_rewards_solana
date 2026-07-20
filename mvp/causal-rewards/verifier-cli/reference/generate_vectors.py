"""Deterministic generator for the golden test vectors.

Run:  python3 generate_vectors.py

Writes test-vectors/serialization/*.json and test-vectors/assignment/*/ with
full canonical bytes and every intermediate hash, so any implementation in any
language can diff step by step. Purely deterministic -- no wall-clock, no RNG.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from canonical import canonical_json_bytes, sha256_hex
from merkle import DOMAIN_ASSIGNMENT, DOMAIN_EVIDENCE, leaf_hash, merkle_root
from assignment import (
    assignment_leaf_bytes,
    assignment_leaf_object,
    cohort_prf,
    derive_assignment,
    seed_commitment,
)

HERE = os.path.dirname(os.path.abspath(__file__))
TV = os.path.abspath(os.path.join(HERE, "..", "..", "test-vectors"))
SPECS = os.path.abspath(os.path.join(HERE, "..", "..", "specs"))


def _write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Human-readable pretty JSON for the vector FILES (these are documentation of
    # the golden values, not themselves hashed artifacts).
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


# --------------------------------------------------------------------------- #
# Serialization vectors
# --------------------------------------------------------------------------- #

SER_CASES = [
    {
        "name": "ser-01-key-ordering",
        "exercises": "object key ordering (UTF-16 code-unit) + array element order preserved",
        "input": {
            "z": "last",
            "a": "first",
            "m": {"beta": "2", "alpha": "1"},
            "list": ["3", "1", "2"],
        },
    },
    {
        "name": "ser-02-unicode-nfc",
        "exercises": "Unicode NFC normalization of keys and values: DECOMPOSED "
        "input (base char + combining mark) must serialize to the PRECOMPOSED form",
        # Built from explicit DECOMPOSED code points so the vector genuinely
        # exercises NFC regardless of how this source file is saved:
        #   'cafe'   + U+0301 COMBINING ACUTE        -> precomposed c-a-f-e-acute
        #   'resume' + U+0301                        -> precomposed resume-acute
        #   'na' + U+0308 COMBINING DIAERESIS + 'me' -> precomposed n-a-diaeresis-me
        "input": {
            "cafe\u0301": "resume\u0301",
            "na\u0308me": "stra\u00dfe",
        },
    },
    {
        "name": "ser-03-decimal-scaling",
        "exercises": "all numeric values carried as strings (no JSON number tokens); "
        "scaled fixed-point integers and negative/zero cases",
        "input": {
            "effect_ppm": "-125000",
            "reward_lamports": "1000000000",
            "std_error_ppm": "0",
            "leading_zero_ppm": "007",
            "big_uint": "18446744073709551615",
        },
    },
    {
        "name": "ser-04-control-and-escapes",
        "exercises": "minimal string escaping: quote, backslash, control chars",
        "input": {"s": "line1\nline2\ttab\"quote\"back\\slashx"},
    },
    {
        "name": "ser-05-nested-mixed",
        "exercises": "nested objects/arrays, booleans, null, empty object/array",
        "input": {
            "flag_true": True,
            "flag_false": False,
            "nothing": None,
            "empty_obj": {},
            "empty_arr": [],
            "nested": [{"b": "2", "a": "1"}, {"a": "3"}],
        },
    },
]


def gen_serialization() -> None:
    index = []
    for case in SER_CASES:
        cb = canonical_json_bytes(case["input"])
        rec = {
            "name": case["name"],
            "spec_section": "canonical-serialization.md",
            "exercises": case["exercises"],
            "input": case["input"],
            "canonical_bytes_utf8": cb.decode("utf-8"),
            "canonical_bytes_hex": cb.hex(),
            "canonical_length": str(len(cb)),
            "sha256_hex": sha256_hex(cb),
        }
        _write_json(os.path.join(TV, "serialization", case["name"] + ".json"), rec)
        index.append({"name": case["name"], "sha256_hex": rec["sha256_hex"], "exercises": case["exercises"]})
    _write_json(os.path.join(TV, "serialization", "index.json"), {"vectors": index})


# --------------------------------------------------------------------------- #
# Assignment vectors
# --------------------------------------------------------------------------- #

# Fixed 32-byte seeds (hex). These are the REVEALED seeds; each vector shows the
# commitment(seed) that would have been frozen in the manifest.
ASSIGN_CASES = [
    {
        "name": "assign-01-bernoulli-p50",
        "exercises": "bernoulli design, treat_fraction 0.5, 4 cohorts; commitment(seed) "
        "and seed->assignment shown as distinct steps",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "00" * 32,
        "cohort_ids": ["cohort-0001", "cohort-0002", "cohort-0003", "cohort-0004"],
        "design": "bernoulli",
        "params": {"treat_fraction_ppm": "500000"},
    },
    {
        "name": "assign-02-fixed-count-2of5",
        "exercises": "fixed_count design, exactly 2 of 5 cohorts treated (exact balance, "
        "prf-ranked, cohort_id tie-break)",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
        "0f1e2d3c4b5a69788796a5b4c3d2e1f0",
        "cohort_ids": ["cohort-A", "cohort-B", "cohort-C", "cohort-D", "cohort-E"],
        "design": "fixed_count",
        "params": {"treatment_count": "2"},
    },
    {
        "name": "assign-03-bernoulli-p25",
        "exercises": "bernoulli design, treat_fraction 0.25, 6 cohorts, different seed "
        "(control-heavy expected)",
        "experiment_id": "exp-2026-switchback-007",
        "seed_hex": "ffeeddccbbaa99887766554433221100"
        "112233445566778899aabbccddeeff00",
        "cohort_ids": [
            "geo-11-t0",
            "geo-11-t1",
            "geo-22-t0",
            "geo-22-t1",
            "geo-33-t0",
            "geo-33-t1",
        ],
        "design": "bernoulli",
        "params": {"treat_fraction_ppm": "250000"},
    },
    {
        "name": "assign-04-bernoulli-p0-allcontrol",
        "exercises": "bernoulli boundary treat_fraction_ppm=0 -> EVERY cohort control "
        "(no positive payout possible); 4 cohorts",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "00" * 32,
        "cohort_ids": ["cohort-0001", "cohort-0002", "cohort-0003", "cohort-0004"],
        "design": "bernoulli",
        "params": {"treat_fraction_ppm": "0"},
    },
    {
        "name": "assign-05-bernoulli-p1000000-alltreat",
        "exercises": "bernoulli boundary treat_fraction_ppm=1000000 -> EVERY cohort "
        "treatment; 4 cohorts",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "00" * 32,
        "cohort_ids": ["cohort-0001", "cohort-0002", "cohort-0003", "cohort-0004"],
        "design": "bernoulli",
        "params": {"treat_fraction_ppm": "1000000"},
    },
    {
        "name": "assign-06-fixed-count-0of5-allcontrol",
        "exercises": "fixed_count boundary treatment_count=0 -> EVERY cohort control; "
        "5 cohorts",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
        "0f1e2d3c4b5a69788796a5b4c3d2e1f0",
        "cohort_ids": ["cohort-A", "cohort-B", "cohort-C", "cohort-D", "cohort-E"],
        "design": "fixed_count",
        "params": {"treatment_count": "0"},
    },
    {
        "name": "assign-07-fixed-count-5of5-alltreat",
        "exercises": "fixed_count boundary treatment_count=n -> EVERY cohort treatment; "
        "5 cohorts",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "0f1e2d3c4b5a69788796a5b4c3d2e1f0"
        "0f1e2d3c4b5a69788796a5b4c3d2e1f0",
        "cohort_ids": ["cohort-A", "cohort-B", "cohort-C", "cohort-D", "cohort-E"],
        "design": "fixed_count",
        "params": {"treatment_count": "5"},
    },
    {
        "name": "assign-08-bernoulli-single-cohort",
        "exercises": "single-leaf tree: assignment_root == leaf_hash(sole leaf), no "
        "interior node; n=1 (Merkle base case)",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "00" * 32,
        "cohort_ids": ["cohort-solo"],
        "design": "bernoulli",
        "params": {"treat_fraction_ppm": "500000"},
    },
    {
        "name": "assign-09-fixed-count-lexical-order",
        "exercises": "cohort_id ordering is UTF-16 code-unit LEXICAL, not numeric: "
        "'cohort-10' sorts BEFORE 'cohort-2'. Inputs supplied SCRAMBLED to prove the "
        "derivation reorders deterministically. fixed_count 3 of 6. This is the "
        "cross-language ordering footgun (naive numeric sort diverges here).",
        "experiment_id": "exp-2026-switchback-007",
        "seed_hex": "aabbccddeeff0011223344556677889"
        "9aabbccddeeff00112233445566778899",
        "cohort_ids": [
            "cohort-2",
            "cohort-10",
            "cohort-1",
            "cohort-20",
            "cohort-3",
            "cohort-11",
        ],
        "design": "fixed_count",
        "params": {"treatment_count": "3"},
    },
    {
        "name": "assign-10-bernoulli-16cohorts",
        "exercises": "16 cohorts, balanced power-of-2 tree (4 levels, no promotion); "
        "bernoulli 0.5; zero-padded ids so lexical order == numeric order",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "00" * 31 + "01",
        "cohort_ids": ["cohort-%02d" % i for i in range(16)],
        "design": "bernoulli",
        "params": {"treat_fraction_ppm": "500000"},
    },
    {
        "name": "assign-11-fixed-count-3of7",
        "exercises": "7 cohorts (odd) exercises odd-node PROMOTION at multiple levels; "
        "fixed_count exactly 3 treated",
        "experiment_id": "exp-2026-envsensors-001",
        "seed_hex": "123456789abcdef0123456789abcdef0"
        "123456789abcdef0123456789abcdef0",
        "cohort_ids": [
            "g-0",
            "g-1",
            "g-2",
            "g-3",
            "g-4",
            "g-5",
            "g-6",
        ],
        "design": "fixed_count",
        "params": {"treatment_count": "3"},
    },
]


def gen_assignment() -> None:
    index = []
    for case in ASSIGN_CASES:
        seed = bytes.fromhex(case["seed_hex"])
        exp = case["experiment_id"]

        # Step 1: commitment (frozen in manifest, before reveal).
        commitment = seed_commitment(seed)

        # Step 2: per-cohort PRF (auditable intermediate).
        prf_steps = []
        for cid in case["cohort_ids"]:
            prf_steps.append(
                {
                    "cohort_id": cid,
                    "prf_u64": str(cohort_prf(seed, exp, cid)),
                }
            )

        # Step 3: derive assignment (canonical cohort-id order).
        assigns = derive_assignment(
            seed, exp, case["cohort_ids"], case["design"], case["params"]
        )

        # Step 4: per-leaf canonical bytes + leaf hash (in canonical order).
        leaf_records = []
        leaf_bytes_list: List[bytes] = []
        for a in assigns:
            lb = assignment_leaf_bytes(a)
            leaf_bytes_list.append(lb)
            lh = leaf_hash(DOMAIN_ASSIGNMENT, lb)
            leaf_records.append(
                {
                    "cohort_id": a.cohort_id,
                    "arm": a.arm,
                    "prf_u64": str(a.prf_u64),
                    "leaf_object": assignment_leaf_object(a),
                    "leaf_canonical_bytes_utf8": lb.decode("utf-8"),
                    "leaf_canonical_bytes_hex": lb.hex(),
                    "leaf_hash_hex": lh.hex(),
                }
            )

        # Step 5: root.
        root = merkle_root(leaf_bytes_list, DOMAIN_ASSIGNMENT)

        n_treat = sum(1 for a in assigns if a.arm == "treatment")

        rec: Dict[str, Any] = {
            "name": case["name"],
            "spec_section": "canonical-serialization.md (Merkle + assignment derivation)",
            "exercises": case["exercises"],
            "inputs": {
                "experiment_id": exp,
                "seed_hex": case["seed_hex"],
                "cohort_ids": case["cohort_ids"],
                "design": case["design"],
                "params": case["params"],
            },
            "step1_seed_commitment": {
                "domain": "CRP-seed-commit-v1",
                "note": "commitment = SHA-256(domain || seed); this is what the "
                "frozen manifest commits to, BEFORE the seed is revealed",
                "seed_commitment_hex": commitment.hex(),
            },
            "step2_cohort_prf": {
                "domain": "CRP-assign-v1",
                "note": "prf_u64 = int(SHA-256(domain || seed || u32be(len exp) || "
                "exp || u32be(len cohort) || cohort)[:8], big-endian)",
                "values": prf_steps,
            },
            "step3_summary": {
                "treatment_count": str(n_treat),
                "control_count": str(len(assigns) - n_treat),
            },
            "step4_leaves": {
                "merkle_domain_tag": "CRP:assignment:v1",
                "leaf_hash_formula": "SHA-256(0x00 || domain_tag || leaf_canonical_bytes)",
                "node_hash_formula": "SHA-256(0x01 || left || right)",
                "leaf_order": "cohort_id ascending (UTF-16 code-unit)",
                "leaves": leaf_records,
            },
            "step5_assignment_root": {
                "assignment_root_hex": root.hex(),
            },
        }
        _write_json(os.path.join(TV, "assignment", case["name"], "vector.json"), rec)
        index.append(
            {
                "name": case["name"],
                "assignment_root_hex": root.hex(),
                "seed_commitment_hex": commitment.hex(),
                "exercises": case["exercises"],
            }
        )
    _write_json(os.path.join(TV, "assignment", "index.json"), {"vectors": index})


# --------------------------------------------------------------------------- #
# Adversarial (negative) fixtures
#
# Each fixture is a bundle/state that a conforming program AND the verifier MUST
# REJECT. It carries: the offending input, why it must be rejected, the exact
# invariant + state-machine/serialization guard that forbids it, a stable
# rejection_code, and a machine-checkable `check` predicate that verify_vectors
# re-evaluates to PROVE the input really is bad (a fixture that fails to be
# rejectable is itself a bug). These define "adversarial tests green" at the M2
# gate: the on-chain programs must reject each of these.
# --------------------------------------------------------------------------- #


def gen_adversarial() -> None:
    fixtures = []

    # ------------------------------------------------------------------ #
    # (a) invalid seed reveal — structural test of freeze-before-reveal.
    # ------------------------------------------------------------------ #
    true_seed = bytes.fromhex("00" * 32)  # what was actually committed pre-freeze
    frozen_commit = seed_commitment(true_seed).hex()
    wrong_seed_hex = "11" * 32  # a DIFFERENT seed the coordinator tries to reveal
    wrong_commit = seed_commitment(bytes.fromhex(wrong_seed_hex)).hex()
    fixtures.append(
        {
            "name": "adv-01-invalid-seed-reveal",
            "category": "invalid-seed-reveal",
            "invariant": "1 (freeze-before-reveal)",
            "spec_refs": [
                "serialization.md §7.2 (seed commitment = SHA-256(CRP-seed-commit-v1 || seed))",
                "state-machine.md §2 transition 4 (reveal_seed)",
            ],
            "guard": "reveal_seed guard: SHA-256(CRP-seed-commit-v1 || revealed_seed) MUST "
            "equal the frozen seed_commitment; else revert.",
            "expected_result": "reject",
            "rejection_code": "SEED_COMMITMENT_MISMATCH",
            "why_rejected": "The revealed seed does not open the commitment frozen in the "
            "manifest. Accepting it would let the coordinator choose a seed AFTER freeze to "
            "steer cohort assignment, breaking freeze-before-reveal.",
            "inputs": {
                "experiment_id": "exp-2026-envsensors-001",
                "frozen_seed_commitment_hex": frozen_commit,
                "revealed_seed_hex": wrong_seed_hex,
            },
            "expected": {
                "recomputed_commitment_of_revealed_seed_hex": wrong_commit,
                "equals_frozen_commitment": False,
            },
            "check": {"kind": "seed_commitment_mismatch"},
        }
    )

    # ------------------------------------------------------------------ #
    # (b) duplicate / overlapping evidence epoch — replayed epoch_index.
    # ------------------------------------------------------------------ #
    fixtures.append(
        {
            "name": "adv-02-duplicate-evidence-epoch",
            "category": "duplicate-evidence-epoch",
            "invariant": "2 (determinism / no unordered replay); append-only evidence epochs",
            "spec_refs": [
                "state-machine.md §2 transition 5 (post_evidence_epoch)",
                "state-machine.md §3 (EvidenceEpoch is write-once / append-only)",
            ],
            "guard": "post_evidence_epoch guard: epoch_index MUST equal previous_epoch_index + 1.",
            "expected_result": "reject",
            "rejection_code": "EPOCH_INDEX_NOT_MONOTONIC",
            "why_rejected": "A second epoch re-uses an already-anchored epoch_index (replay) "
            "instead of extending the chain by exactly one. Anchoring it would duplicate or "
            "overwrite a committed epoch and let the same evidence be counted twice.",
            "inputs": {
                "experiment_id": "env-sensors-pilot-001",
                "previous_epoch_index": "3",
                "attempted_epoch_index": "3",
            },
            "expected": {
                "required_next_epoch_index": "4",
                "attempted_equals_required": False,
            },
            "check": {"kind": "epoch_index_not_monotonic"},
        }
    )

    # ------------------------------------------------------------------ #
    # (b') replayed evidence batch — byte-identical batch twice in one epoch.
    #      §6.5: evidence epoch tree requires STRICT monotonic leaf_hash order;
    #      two identical batches collide on leaf_hash => hard error.
    # ------------------------------------------------------------------ #
    batch = json.load(
        open(os.path.join(SPECS, "examples", "evidence.example.json"), encoding="utf-8")
    )
    batch_leaf = leaf_hash(DOMAIN_EVIDENCE, canonical_json_bytes(batch)).hex()
    fixtures.append(
        {
            "name": "adv-03-replayed-evidence-batch",
            "category": "duplicate-evidence-epoch",
            "invariant": "2 (determinism); §6.5 evidence-tree totality (duplicate batch = hard error)",
            "spec_refs": [
                "serialization.md §6.5 (evidence epoch tree; sort key = leaf_hash ascending; "
                "byte-identical batch leaves are a hard error → strict total order)",
            ],
            "guard": "Evidence epoch tree requires STRICTLY increasing leaf_hash order. Two "
            "byte-identical batch headers produce the same leaf_hash → not strictly "
            "increasing → reject.",
            "expected_result": "reject",
            "rejection_code": "DUPLICATE_EVIDENCE_LEAF",
            "why_rejected": "The same signed batch is submitted twice within one epoch. "
            "Byte-identical batch objects hash to the same leaf_hash; the tree's strict "
            "ordering rejects the duplicate, preventing double-counting of the same evidence.",
            "inputs": {
                "evidence_domain_tag": "CRP:evidence:v1",
                "batch_a": batch,
                "batch_b": batch,
            },
            "expected": {
                "batch_a_leaf_hash_hex": batch_leaf,
                "batch_b_leaf_hash_hex": batch_leaf,
                "leaf_hashes_equal": True,
            },
            "check": {"kind": "duplicate_evidence_leaf"},
        }
    )

    # ------------------------------------------------------------------ #
    # (c) stale evaluation — references a superseded committed state.
    #     committed cohort_root = assign-01's root; the evaluation references a
    #     different (superseded) root, e.g. after an upheld-challenge re-derive.
    # ------------------------------------------------------------------ #
    committed_root = merkle_root(
        [
            assignment_leaf_bytes(a)
            for a in derive_assignment(
                bytes.fromhex("00" * 32),
                "exp-2026-envsensors-001",
                ["cohort-0001", "cohort-0002", "cohort-0003", "cohort-0004"],
                "bernoulli",
                {"treat_fraction_ppm": "500000"},
            )
        ],
        DOMAIN_ASSIGNMENT,
    ).hex()
    superseded_root = merkle_root(
        [
            assignment_leaf_bytes(a)
            for a in derive_assignment(
                bytes.fromhex("ffeeddccbbaa99887766554433221100112233445566778899aabbccddeeff00"),
                "exp-2026-switchback-007",
                ["geo-11-t0", "geo-11-t1", "geo-22-t0", "geo-22-t1", "geo-33-t0", "geo-33-t1"],
                "bernoulli",
                {"treat_fraction_ppm": "250000"},
            )
        ],
        DOMAIN_ASSIGNMENT,
    ).hex()
    fixtures.append(
        {
            "name": "adv-04-stale-evaluation",
            "category": "stale-evaluation",
            "invariant": "2 (reproducibility); evaluation binds the CURRENT committed state",
            "spec_refs": [
                "state-machine.md §2 transition 6 (submit_evaluation)",
                "state-machine.md §2 transition 8 (resolve_challenge: an upheld challenge "
                "invalidates the Evaluation, so a re-submission must bind current state)",
            ],
            "guard": "An Evaluation must be computed against the CURRENTLY committed "
            "cohort_root / epoch set. One referencing a superseded root (e.g. the pre-"
            "re-derivation root after an upheld challenge) is stale and must be rejected.",
            "expected_result": "reject",
            "rejection_code": "STALE_EVALUATION_STATE_MISMATCH",
            "why_rejected": "The evaluation's referenced cohort_root does not match the "
            "cohort_root committed on-chain for this experiment. Accepting it would settle "
            "rewards against a superseded assignment, breaking reproducibility.",
            "inputs": {
                "experiment_id": "exp-2026-envsensors-001",
                "committed_cohort_root_hex": committed_root,
                "evaluation_referenced_cohort_root_hex": superseded_root,
            },
            "expected": {"referenced_matches_committed": False},
            "check": {"kind": "stale_evaluation_state_mismatch"},
        }
    )

    # ------------------------------------------------------------------ #
    # (c') evaluation with wrong analysis-container digest — breaks the pinned
    #      reproducibility container (part of the frozen immutability set).
    # ------------------------------------------------------------------ #
    frozen_digest = "sha256:" + "ab" * 32
    echoed_digest = "sha256:" + "cd" * 32
    fixtures.append(
        {
            "name": "adv-05-evaluation-container-mismatch",
            "category": "stale-evaluation",
            "invariant": "2 (reproducibility via pinned container); 6 (process verified, not truth)",
            "spec_refs": [
                "state-machine.md §2 transition 6 (submit_evaluation: echoed "
                "analysis_container_digest MUST equal the frozen one)",
                "state-machine.md §3 (analysis_container_digest is in the frozen immutability set)",
            ],
            "guard": "submit_evaluation guard: the echoed analysis_container_digest MUST "
            "equal the frozen analysis_container_digest.",
            "expected_result": "reject",
            "rejection_code": "CONTAINER_DIGEST_MISMATCH",
            "why_rejected": "The evaluation was produced by a container whose digest differs "
            "from the one pinned at freeze. A different container can produce a different "
            "result artifact, so the result is not reproducible against the frozen plan.",
            "inputs": {
                "experiment_id": "exp-2026-envsensors-001",
                "frozen_analysis_container_digest": frozen_digest,
                "echoed_analysis_container_digest": echoed_digest,
            },
            "expected": {"digests_equal": False},
            "check": {"kind": "container_digest_mismatch"},
        }
    )

    # ------------------------------------------------------------------ #
    # (d) double claim — same reward-leaf nullifier claimed twice.
    # ------------------------------------------------------------------ #
    nullifier_hex = sha256_hex(
        canonical_json_bytes({"cohort_id": "cohort-0001", "recipient": "P-001"})
    )
    fixtures.append(
        {
            "name": "adv-06-double-claim",
            "category": "double-claim",
            "invariant": "single-use claims (settlement); ClaimReceipt is a write-once nullifier",
            "spec_refs": [
                "state-machine.md §2 transition 10 (claim_reward: no existing ClaimReceipt "
                "for that leaf / nullifier unused)",
                "state-machine.md §3 (ClaimReceipt is a write-once nullifier)",
            ],
            "guard": "claim_reward guard: there MUST be no existing ClaimReceipt for the "
            "reward leaf (its nullifier must be unused).",
            "expected_result": "reject",
            "rejection_code": "NULLIFIER_ALREADY_USED",
            "why_rejected": "The second claim re-uses the same reward-leaf nullifier already "
            "recorded by the first ClaimReceipt. Accepting it would pay the same leaf twice "
            "(double spend of the reward budget).",
            "inputs": {
                "experiment_id": "exp-2026-envsensors-001",
                "reward_root_hex": "00" * 32,
                "first_claim": {"nullifier_hex": nullifier_hex, "amount_base_units": "1000"},
                "second_claim": {"nullifier_hex": nullifier_hex, "amount_base_units": "1000"},
            },
            "expected": {"nullifiers_equal": True},
            "check": {"kind": "double_claim_nullifier_reuse"},
        }
    )

    index = []
    for fx in fixtures:
        _write_json(os.path.join(TV, "adversarial", fx["name"] + ".json"), fx)
        index.append(
            {
                "name": fx["name"],
                "category": fx["category"],
                "expected_result": fx["expected_result"],
                "rejection_code": fx["rejection_code"],
                "invariant": fx["invariant"],
            }
        )
    _write_json(os.path.join(TV, "adversarial", "index.json"), {"fixtures": index})


if __name__ == "__main__":
    gen_serialization()
    gen_assignment()
    gen_adversarial()
    print("vectors written to", TV)
