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
from merkle import DOMAIN_ASSIGNMENT, leaf_hash, merkle_root
from assignment import (
    assignment_leaf_bytes,
    assignment_leaf_object,
    cohort_prf,
    derive_assignment,
    seed_commitment,
)

HERE = os.path.dirname(os.path.abspath(__file__))
TV = os.path.abspath(os.path.join(HERE, "..", "..", "test-vectors"))


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


if __name__ == "__main__":
    gen_serialization()
    gen_assignment()
    print("vectors written to", TV)
