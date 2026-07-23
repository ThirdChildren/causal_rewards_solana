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
    parse_composite_cohort_id,
    round_half_even_div,
    seed_commitment,
    switchback_phase,
)
import reward as reward_mod
import evidence as evidence_mod

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
    # v1.1 §7.4 derivations share the same assignment index and tree/leaf shape.
    gen_assignment_switchback(index)
    gen_assignment_matched(index)
    _write_json(os.path.join(TV, "assignment", "index.json"), {"vectors": index})


# --------------------------------------------------------------------------- #
# Assignment vectors — switchback + matched_cluster (v1.1 §7.4 derivations)
# --------------------------------------------------------------------------- #

# switchback: composite `group"|"index` ids; phase(group) = prf(group)&1;
# arm = treatment iff (index + phase) % 2 == 1. treated_fraction_micro MUST be "500000".
ASSIGN_SWITCHBACK_CASES = [
    {
        "name": "assign-12-switchback-2geo-2period",
        "exercises": "switchback design: 2 geo-cohorts x 2 periods. Per-geo randomized "
        "phase bit + parity alternation across periods; arm flips every period within a "
        "geo. treated_fraction_micro MUST be 500000. Leaf carries the FULL composite "
        "cohort_id and leaves sort by the FULL id (§7.5/§6.2).",
        "experiment_id": "exp-2026-switchback-007",
        "seed_hex": "1111111111111111111111111111111111111111111111111111111111111111",
        "cohort_ids": ["geo-11|0", "geo-11|1", "geo-22|0", "geo-22|1"],
        "params": {"treated_fraction_micro": "500000"},
    },
    {
        "name": "assign-13-switchback-3geo-noncontiguous",
        "exercises": "switchback with 3 geo-cohorts and NON-CONTIGUOUS period indices "
        "(arm is a pure function of (group,index) regardless of gaps). Different seed; "
        "odd total leaf count (5) exercises odd-node promotion in the assignment tree.",
        "experiment_id": "exp-2026-switchback-007",
        "seed_hex": "a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff00",
        "cohort_ids": ["geo-a|0", "geo-a|2", "geo-a|5", "geo-b|1", "geo-c|0"],
        "params": {"treated_fraction_micro": "500000"},
    },
]

# matched_cluster: per-stratum k_s = round_he(frac * m_s / 1e6) clamped [0,m_s],
# ranked by (prf_u64(FULL id), member_index); first k_s treated.
ASSIGN_MATCHED_CASES = [
    {
        "name": "assign-14-matched-pairs-2x2",
        "exercises": "matched_cluster canonical MATCHED PAIRS: two strata, each m_s=2, "
        "treated_fraction_micro=500000 -> k_s=round_he(1.0)=1 (exactly one of each pair "
        "treated). Ranked by (full-id prf, member_index).",
        "experiment_id": "exp-2026-matched-009",
        "seed_hex": "2222222222222222222222222222222222222222222222222222222222222222",
        "cohort_ids": ["pair-1|0", "pair-1|1", "pair-2|0", "pair-2|1"],
        "params": {"treated_fraction_micro": "500000"},
    },
    {
        "name": "assign-15-matched-mixed-strata-halfeven",
        "exercises": "matched_cluster mixed strata exercising round-half-to-EVEN at the "
        "exact .5 tie: stratum sA has m_s=3, frac=500000 -> 1.5 -> k_s=2 (q=1 odd -> q+1); "
        "stratum sB has m_s=2 -> k_s=1. Proves banker's rounding + clamp, and per-stratum "
        "independence.",
        "experiment_id": "exp-2026-matched-009",
        "seed_hex": "3333333333333333333333333333333333333333333333333333333333333333",
        "cohort_ids": ["sA|0", "sA|1", "sA|2", "sB|0", "sB|1"],
        "params": {"treated_fraction_micro": "500000"},
    },
]


def _assignment_common(case, design):
    seed = bytes.fromhex(case["seed_hex"])
    exp = case["experiment_id"]
    commitment = seed_commitment(seed)
    # Full-composite-id PRF for every cohort (auditable intermediate; the actual
    # decision input per design is shown in the design-specific block).
    prf_steps = [
        {"cohort_id": cid, "prf_u64": str(cohort_prf(seed, exp, cid))}
        for cid in case["cohort_ids"]
    ]
    assigns = derive_assignment(seed, exp, case["cohort_ids"], design, case["params"])
    leaf_records = []
    leaf_bytes_list = []
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
    root = merkle_root(leaf_bytes_list, DOMAIN_ASSIGNMENT)
    n_treat = sum(1 for a in assigns if a.arm == "treatment")
    rec = {
        "name": case["name"],
        "spec_section": "serialization.md §7.4 (%s derivation) + §6/§7.5 (assignment tree)"
        % design,
        "exercises": case["exercises"],
        "inputs": {
            "experiment_id": exp,
            "seed_hex": case["seed_hex"],
            "cohort_ids": case["cohort_ids"],
            "design": design,
            "params": case["params"],
        },
        "step1_seed_commitment": {
            "domain": "CRP-seed-commit-v1",
            "note": "commitment = SHA-256(domain || seed); frozen BEFORE the seed is revealed",
            "seed_commitment_hex": commitment.hex(),
        },
        "step2_cohort_prf": {
            "domain": "CRP-assign-v1",
            "note": "prf_u64(FULL composite cohort_id) = int(SHA-256(domain || seed || "
            "u32be(len exp) || exp || u32be(len cohort) || cohort)[:8], big-endian). "
            "Auditable intermediate; the per-design decision input is in the design block.",
            "values": prf_steps,
        },
    }
    return seed, exp, assigns, leaf_bytes_list, leaf_records, root, n_treat, rec


def gen_assignment_switchback(index):
    for case in ASSIGN_SWITCHBACK_CASES:
        seed, exp, assigns, _lb, leaf_records, root, n_treat, rec = _assignment_common(
            case, "switchback"
        )
        # Per-geo phase table (the switchback randomization unit).
        groups = []
        seen = set()
        for cid in case["cohort_ids"]:
            group, _idx = parse_composite_cohort_id(cid)
            if group in seen:
                continue
            seen.add(group)
            groups.append(
                {
                    "group": group,
                    "group_prf_u64": str(cohort_prf(seed, exp, group)),
                    "phase": str(switchback_phase(seed, exp, group)),
                }
            )
        periods = []
        for cid in case["cohort_ids"]:
            group, idx = parse_composite_cohort_id(cid)
            ph = switchback_phase(seed, exp, group)
            periods.append(
                {
                    "cohort_id": cid,
                    "group": group,
                    "index": str(idx),
                    "phase": str(ph),
                    "index_plus_phase_mod2": str((idx + ph) % 2),
                    "arm": "treatment" if (idx + ph) % 2 == 1 else "control",
                }
            )
        rec["step2b_switchback_derivation"] = {
            "note": "phase(group) = prf_u64(group) & 1; arm = treatment iff "
            "(index + phase) % 2 == 1. treated_fraction_micro MUST be '500000' "
            "(asserted, not read by the derivation).",
            "treated_fraction_micro_asserted": case["params"]["treated_fraction_micro"],
            "per_group_phase": groups,
            "per_unit_arm": periods,
        }
        rec["step3_summary"] = {
            "treatment_count": str(n_treat),
            "control_count": str(len(assigns) - n_treat),
        }
        rec["step4_leaves"] = {
            "merkle_domain_tag": "CRP:assignment:v1",
            "leaf_hash_formula": "SHA-256(0x00 || domain_tag || leaf_canonical_bytes)",
            "node_hash_formula": "SHA-256(0x01 || left || right)",
            "leaf_order": "FULL composite cohort_id ascending (UTF-16 code-unit)",
            "leaves": leaf_records,
        }
        rec["step5_assignment_root"] = {"assignment_root_hex": root.hex()}
        _write_json(os.path.join(TV, "assignment", case["name"], "vector.json"), rec)
        index.append(
            {
                "name": case["name"],
                "assignment_root_hex": root.hex(),
                "seed_commitment_hex": rec["step1_seed_commitment"]["seed_commitment_hex"],
                "exercises": case["exercises"],
            }
        )


def gen_assignment_matched(index):
    for case in ASSIGN_MATCHED_CASES:
        seed, exp, assigns, _lb, leaf_records, root, n_treat, rec = _assignment_common(
            case, "matched_cluster"
        )
        frac = int(case["params"]["treated_fraction_micro"])
        # Per-stratum k_s + within-stratum ranking.
        strata_map = {}
        for cid in case["cohort_ids"]:
            group, idx = parse_composite_cohort_id(cid)
            strata_map.setdefault(group, []).append(
                (cohort_prf(seed, exp, cid), idx, cid)
            )
        strata_records = []
        arm_by_cid = {a.cohort_id: a.arm for a in assigns}
        for group, members in strata_map.items():
            m_s = len(members)
            k_s = max(0, min(round_half_even_div(frac * m_s, 1_000_000), m_s))
            ranked = sorted(members, key=lambda t: (t[0], t[1]))
            ranked_rows = []
            for pos, (prf_u64, idx, cid) in enumerate(ranked):
                ranked_rows.append(
                    {
                        "rank": str(pos),
                        "cohort_id": cid,
                        "member_index": str(idx),
                        "prf_u64": str(prf_u64),
                        "arm": arm_by_cid[cid],
                    }
                )
            strata_records.append(
                {
                    "group": group,
                    "m_s": str(m_s),
                    "frac_times_m_s": str(frac * m_s),
                    "k_s": str(k_s),
                    "ranked_members": ranked_rows,
                }
            )
        rec["step2b_matched_cluster_derivation"] = {
            "note": "per stratum s: k_s = round_half_even(frac * m_s / 1e6) clamped [0,m_s]; "
            "rank members ascending by (prf_u64(FULL id), member_index); first k_s -> treatment.",
            "treated_fraction_micro": case["params"]["treated_fraction_micro"],
            "per_stratum": strata_records,
        }
        rec["step3_summary"] = {
            "treatment_count": str(n_treat),
            "control_count": str(len(assigns) - n_treat),
        }
        rec["step4_leaves"] = {
            "merkle_domain_tag": "CRP:assignment:v1",
            "leaf_hash_formula": "SHA-256(0x00 || domain_tag || leaf_canonical_bytes)",
            "node_hash_formula": "SHA-256(0x01 || left || right)",
            "leaf_order": "FULL composite cohort_id ascending (UTF-16 code-unit)",
            "leaves": leaf_records,
        }
        rec["step5_assignment_root"] = {"assignment_root_hex": root.hex()}
        _write_json(os.path.join(TV, "assignment", case["name"], "vector.json"), rec)
        index.append(
            {
                "name": case["name"],
                "assignment_root_hex": root.hex(),
                "seed_commitment_hex": rec["step1_seed_commitment"]["seed_commitment_hex"],
                "exercises": case["exercises"],
            }
        )


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


# --------------------------------------------------------------------------- #
# Reward-root vectors (serialization.md §6.6, aggregate-one-leaf-per-recipient)
# --------------------------------------------------------------------------- #

# 32-byte recipient pubkeys as raw hex (native 32-byte form). Chosen so INPUT
# order differs from the sorted (BE32-ascending) leaf order, proving the ranking.
_R_GAMMA = "0a" * 32  # sorts FIRST  (0x0a…)
_R_ALPHA = "11" * 32  # sorts SECOND (0x11…)
_R_DELTA = "33" * 32  # zero-sum in reward-02 (must be dropped despite sorting mid-set)
_R_BETA = "22" * 32   # sorts THIRD  (0x22…)
_R_EPSILON = "44" * 32
_R_ZETA = "77" * 32


def _reward_leaf_rows(leaves):
    rows = []
    for lf in leaves:
        content = reward_mod.reward_leaf_content(
            lf.recipient, lf.amount_base_units, lf.leaf_index
        )
        rows.append(
            {
                "leaf_index": str(lf.leaf_index),
                "recipient_hex": lf.recipient.hex(),
                "amount_base_units": str(lf.amount_base_units),
                "leaf_content_hex": content.hex(),
                "leaf_hash_hex": reward_mod.reward_leaf_hash(
                    lf.recipient, lf.amount_base_units, lf.leaf_index
                ).hex(),
            }
        )
    return rows


def _reward_positive_vector(name, exercises, contributions):
    """contributions: list of {recipient_hex, cohort_id, amount_base_units(str)}."""
    contrib_pairs = [
        (bytes.fromhex(c["recipient_hex"]), int(c["amount_base_units"]))
        for c in contributions
    ]
    aggregate = reward_mod.aggregate_contributions(contrib_pairs)
    leaves = reward_mod.compile_reward_leaves(aggregate)
    dropped = sorted(r.hex() for r, a in aggregate.items() if a == 0)
    root = reward_mod.reward_root(leaves)
    return {
        "name": name,
        "kind": "reward_positive",
        "spec_section": "serialization.md §6.6 + reward-policy.md Stage 2 (aggregate-one-leaf-per-recipient)",
        "exercises": exercises,
        "leaf_hash_formula": "SHA-256(0x00 || 'CRP:reward:v1' || recipient(32) || "
        "amount_base_units(u64 BE) || leaf_index(u64 BE))",
        "node_hash_formula": "SHA-256(0x01 || left || right)",
        "ordering": "aggregate Σ over cohorts per recipient; DROP zero-sum recipients; "
        "rank ascending by recipient(BE32, unique key) then amount_base_units; "
        "leaf_index = 0-based rank; leaves placed by leaf_index contiguous from 0",
        "inputs": {"contributions": contributions},
        "aggregate_recipient_amount_map": {
            r.hex(): str(a) for r, a in sorted(aggregate.items())
        },
        "dropped_zero_sum_recipients_hex": dropped,
        "leaves": _reward_leaf_rows(leaves),
        "reward_root_hex": root.hex(),
    }


def gen_reward():
    index = []
    vectors = []

    # reward-01: multiple recipients, ordering matters, Σ over cohorts.
    vectors.append(
        _reward_positive_vector(
            "reward-01-multi-recipient-ordering",
            "multiple distinct recipients: input order differs from the sorted (recipient "
            "BE32 ascending) leaf order; two recipients each earn across TWO cohorts, "
            "aggregated by integer Σ. Proves ranking + leaf_index assignment + Σ-over-cohorts.",
            [
                {"recipient_hex": _R_BETA, "cohort_id": "cohort-A", "amount_base_units": "70"},
                {"recipient_hex": _R_ALPHA, "cohort_id": "cohort-B", "amount_base_units": "50"},
                {"recipient_hex": _R_GAMMA, "cohort_id": "cohort-C", "amount_base_units": "5"},
                {"recipient_hex": _R_ALPHA, "cohort_id": "cohort-A", "amount_base_units": "100"},
                {"recipient_hex": _R_GAMMA, "cohort_id": "cohort-B", "amount_base_units": "25"},
            ],
        )
    )

    # reward-02: a zero-sum recipient MUST be dropped (even though it sorts mid-set).
    vectors.append(
        _reward_positive_vector(
            "reward-02-zero-sum-dropped",
            "a recipient whose aggregate sum is 0 (its only contribution is 0) is OMITTED "
            "from the leaf set and does NOT consume a leaf_index — even though its recipient "
            "BE32 sorts BETWEEN the two surviving leaves. Confirms zero-sum omission.",
            [
                {"recipient_hex": _R_ALPHA, "cohort_id": "cohort-A", "amount_base_units": "40"},
                {"recipient_hex": _R_DELTA, "cohort_id": "cohort-A", "amount_base_units": "0"},
                {"recipient_hex": _R_EPSILON, "cohort_id": "cohort-B", "amount_base_units": "10"},
            ],
        )
    )

    # reward-03: single-recipient base case (root == the sole leaf_hash).
    vectors.append(
        _reward_positive_vector(
            "reward-03-single-recipient",
            "single-recipient base case: one leaf at leaf_index 0; reward_root == "
            "leaf_hash(sole leaf) (no interior node). Merkle base case for the reward tree.",
            [
                {"recipient_hex": _R_ZETA, "cohort_id": "cohort-A", "amount_base_units": "1000"},
            ],
        )
    )

    # reward-05: empty distribution (all contributions zero) -> empty tree sentinel.
    empty_agg = reward_mod.aggregate_contributions(
        [(bytes.fromhex(_R_ALPHA), 0), (bytes.fromhex(_R_BETA), 0)]
    )
    empty_leaves = reward_mod.compile_reward_leaves(empty_agg)
    empty_root = reward_mod.reward_root(empty_leaves)
    vectors.append(
        {
            "name": "reward-05-empty-all-zero",
            "kind": "reward_empty",
            "spec_section": "serialization.md §6.6 + §6.4 (empty tree)",
            "exercises": "fully-null distribution: every recipient's aggregate is 0, so ALL "
            "are dropped -> empty leaf set -> reward_root = 32 zero bytes (§6.4). "
            "finalize_distribution then locks a zero root and the whole budget is recoverable.",
            "inputs": {
                "contributions": [
                    {"recipient_hex": _R_ALPHA, "cohort_id": "cohort-A", "amount_base_units": "0"},
                    {"recipient_hex": _R_BETA, "cohort_id": "cohort-A", "amount_base_units": "0"},
                ]
            },
            "leaves": [],
            "reward_root_hex": empty_root.hex(),
        }
    )

    # reward-04: HARD ERROR — a leaf set with a DUPLICATE recipient (compiler bug).
    # recipient is a unique key after aggregation; two leaves sharing it is a hard error.
    vectors.append(
        {
            "name": "reward-04-duplicate-recipient-error",
            "kind": "reward_duplicate_recipient_error",
            "spec_section": "serialization.md §6.6 (recipient is a UNIQUE key after aggregation)",
            "exercises": "compiler-bug guard: a reward leaf set containing TWO leaves with the "
            "same recipient is a HARD ERROR (recipient is a unique key; the SDK's "
            "reject-on-ambiguity must fire). Demonstrates the verifier REJECTS malformed "
            "compiler output rather than silently building a tree.",
            "expected_result": "reject",
            "rejection_code": "DUPLICATE_REWARD_RECIPIENT",
            "why_rejected": "After aggregate-one-leaf-per-recipient, `recipient` is a unique "
            "primary key; two leaves sharing it can only be a compiler bug and would also "
            "collide the per-experiment ClaimReceipt nullifier PDA.",
            "inputs": {
                "malformed_leaf_set": [
                    {"recipient_hex": _R_ALPHA, "amount_base_units": "10", "leaf_index": "0"},
                    {"recipient_hex": _R_ALPHA, "amount_base_units": "20", "leaf_index": "1"},
                ]
            },
        }
    )

    for v in vectors:
        _write_json(os.path.join(TV, "reward", v["name"] + ".json"), v)
        entry = {"name": v["name"], "kind": v["kind"]}
        if v["kind"].endswith("_error"):
            entry["expected_result"] = v["expected_result"]
            entry["rejection_code"] = v["rejection_code"]
        else:
            entry["reward_root_hex"] = v["reward_root_hex"]
        index.append(entry)
    _write_json(os.path.join(TV, "reward", "index.json"), {"vectors": index})


# --------------------------------------------------------------------------- #
# Evidence-root vectors (serialization.md §6.5 — OFF-CHAIN source of truth)
# --------------------------------------------------------------------------- #


def _evidence_batch(cohort_id, epoch_index, start, end, sig_byte, signer_pubkey_b58):
    """A schema-shaped evidence batch header (varied so leaf_hashes differ)."""
    hh = sig_byte * 64
    sig = sig_byte * 128
    return {
        "spec_version": "1.0.0",
        "experiment_id": "env-sensors-pilot-001",
        "epoch_index": epoch_index,
        "cohort_id": cohort_id,
        "time_range": {"start": start, "end": end},
        "signer_set_commitment": {
            "algo": "sha256",
            "merkle_root_hex": "a1" * 32,
            "signer_count": "3",
            "leaf_scheme": "sha256(0x00||'signer'||signer_pubkey_be32)",
        },
        "observations_commitment": {
            "algo": "sha256",
            "merkle_root_hex": "b2" * 32,
            "leaf_count": "4",
            "leaf_scheme": "sha256(0x00||'obs'||observation_commitment_be32)",
        },
        "aggregate_summary": {
            "accepted_count": "100",
            "rejected_count": "2",
            "distinct_signers": "3",
        },
        "batch_signature": {
            "algo": "ed25519",
            "signer_pubkey": signer_pubkey_b58,
            "header_hash_hex": hh,
            "signature_hex": sig,
        },
    }


def gen_evidence():
    index = []
    vectors = []

    # A signer pubkey (base58, decodes to exactly 32 bytes) used inside batch headers.
    coord_pk = evidence_mod.b58encode(bytes([0x0C]) + bytes(31))

    # evidence-01: multi-batch epoch tree, ordering by leaf_hash.
    batches = [
        _evidence_batch("cohort-x", "0", "1721001600", "1721088000", "aa", coord_pk),
        _evidence_batch("cohort-y", "0", "1721088000", "1721174400", "bb", coord_pk),
        _evidence_batch("cohort-z", "0", "1721174400", "1721260800", "cc", coord_pk),
    ]
    epoch_root, epoch_records = evidence_mod.epoch_tree(batches)
    # Unsorted per-batch leaf hashes (to make the reordering visible).
    unsorted = []
    for b in batches:
        cb = canonical_json_bytes(b)
        unsorted.append(
            {
                "cohort_id": b["cohort_id"],
                "leaf_canonical_bytes_len": str(len(cb)),
                "leaf_hash_hex": leaf_hash(DOMAIN_EVIDENCE, cb).hex(),
            }
        )
    vectors.append(
        {
            "name": "evidence-01-epoch-multibatch",
            "kind": "evidence_epoch",
            "spec_section": "serialization.md §6.5 (evidence epoch tree; DOMAIN 'CRP:evidence:v1')",
            "exercises": "multi-batch epoch: 3 signed batch headers, leaf = CJSON(batch) "
            "(incl. batch_signature), ordered ASCENDING by leaf_hash before building the "
            "tree. Input order is NOT insertion order — the tree is data-derived.",
            "leaf_hash_formula": "SHA-256(0x00 || 'CRP:evidence:v1' || CJSON(batch))",
            "node_hash_formula": "SHA-256(0x01 || left || right)",
            "sort_key": "leaf_hash ascending (byte-identical batch -> hard error)",
            "inputs": {"batches": batches},
            "unsorted_leaf_hashes": unsorted,
            "ordered_leaves": epoch_records,
            "evidence_epoch_root_hex": epoch_root.hex(),
        }
    )

    # evidence-02: multi-signer set sub-commitment (leaf domain 'signer').
    # Raw first bytes chosen so INPUT order != sorted BE32 order.
    signer_raw = [
        bytes([0x30]) + bytes(31),
        bytes([0x05]) + bytes(31),
        bytes([0x99]) + bytes(31),
        bytes([0x50]) + bytes(31),
    ]
    signer_b58 = [evidence_mod.b58encode(r) for r in signer_raw]
    signer_root, signer_records = evidence_mod.signer_subtree(signer_b58)
    vectors.append(
        {
            "name": "evidence-02-signer-set-multisigner",
            "kind": "evidence_signer_set",
            "spec_section": "serialization.md §6.5 (signer set sub-commitment; leaf domain 'signer')",
            "exercises": "signer-set sub-commitment over 4 ed25519 signer pubkeys. Each "
            "signer_pubkey is base58-decoded to EXACTLY 32 bytes (hard error otherwise), "
            "sorted ASCENDING by the 32-byte pubkey (BE), then hashed. Input order != sorted.",
            "leaf_hash_formula": "SHA-256(0x00 || 'signer' || signer_pubkey_be32)",
            "node_hash_formula": "SHA-256(0x01 || left || right)",
            "sort_key": "signer_pubkey_be32 ascending (duplicate pubkey -> hard error)",
            "inputs": {"signer_pubkeys_base58": signer_b58},
            "ordered_leaves": signer_records,
            "signer_set_root_hex": signer_root.hex(),
        }
    )

    # evidence-03: multi-observation set sub-commitment (leaf domain 'obs').
    obs_hexes = [
        "70" + "00" * 31,
        "0f" + "ff" * 31,
        "40" + "11" * 31,
        "40" + "10" * 31,
    ]
    obs_root, obs_records = evidence_mod.observation_subtree(obs_hexes)
    vectors.append(
        {
            "name": "evidence-03-observation-set",
            "kind": "evidence_observation_set",
            "spec_section": "serialization.md §6.5 (observation sub-commitment; leaf domain 'obs')",
            "exercises": "observation sub-commitment over 4 per-observation content "
            "commitments (32 raw bytes each from payload_commitment_hex ^[0-9a-f]{64}$), "
            "sorted ASCENDING by the 32-byte commitment (BE). Includes a tight adjacent "
            "pair (0x40 10.. vs 0x40 11..) to exercise byte-lexicographic ordering.",
            "leaf_hash_formula": "SHA-256(0x00 || 'obs' || observation_commitment_be32)",
            "node_hash_formula": "SHA-256(0x01 || left || right)",
            "sort_key": "observation_commitment_be32 ascending (duplicate -> hard error)",
            "inputs": {"payload_commitment_hexes": obs_hexes},
            "ordered_leaves": obs_records,
            "observations_root_hex": obs_root.hex(),
        }
    )

    # evidence-04: empty-tree sentinel (32 zero bytes) — domain-independent (§6.4).
    z = "00" * 32
    assert evidence_mod.epoch_tree([])[0].hex() == z
    assert evidence_mod.signer_subtree([])[0].hex() == z
    assert evidence_mod.observation_subtree([])[0].hex() == z
    vectors.append(
        {
            "name": "evidence-04-empty-tree",
            "kind": "evidence_empty_tree",
            "spec_section": "serialization.md §6.4 (empty tree) + §6.5",
            "exercises": "empty-tree sentinel: an evidence tree (epoch / signer / observation) "
            "with ZERO leaves has root = 32 zero bytes — an unmistakable 'nothing committed' "
            "sentinel, never SHA-256(DOMAIN_TAG).",
            "inputs": {"leaves": []},
            "empty_root_hex": z,
        }
    )

    # evidence-05: HARD ERROR — signer_pubkey base58-decodes to != 32 bytes.
    # A base58 encoding of a 33-byte value: the {32,44}-CHAR regex would pass, but the
    # 32-byte length pin (§6.5) rejects it.
    bad_pk = evidence_mod.b58encode(bytes([0x01]) + bytes(32))  # 33 bytes -> hard error
    decoded_len = len(evidence_mod.b58decode(bad_pk))
    vectors.append(
        {
            "name": "evidence-05-signer-not-32-error",
            "kind": "evidence_signer_not_32_error",
            "spec_section": "serialization.md §6.5 (signer_pubkey MUST base58-decode to EXACTLY 32 bytes)",
            "exercises": "hard-error guard: a signer_pubkey that base58-decodes to a "
            "NON-32-byte value (here 33 bytes) is rejected before ordering. The {32,44}-"
            "CHARACTER schema regex does not exclude this; the §6.5 length pin does. Prevents "
            "on-chain vs off-chain divergence on a fixed-width 32-byte sort key.",
            "expected_result": "reject",
            "rejection_code": "SIGNER_PUBKEY_NOT_32_BYTES",
            "why_rejected": "signer_pubkey_be32 must be exactly 32 bytes for the fixed-width "
            "sol_memcmp/BE sort key; a 31/33-byte decode diverges on-chain vs off-chain and "
            "admits an invalid pubkey.",
            "inputs": {
                "signer_pubkey_base58": bad_pk,
                "base58_decoded_length": str(decoded_len),
            },
        }
    )

    for v in vectors:
        _write_json(os.path.join(TV, "evidence", v["name"] + ".json"), v)
        entry = {"name": v["name"], "kind": v["kind"]}
        if v["kind"].endswith("_error"):
            entry["expected_result"] = v["expected_result"]
            entry["rejection_code"] = v["rejection_code"]
        elif v["kind"] == "evidence_epoch":
            entry["evidence_epoch_root_hex"] = v["evidence_epoch_root_hex"]
        elif v["kind"] == "evidence_signer_set":
            entry["signer_set_root_hex"] = v["signer_set_root_hex"]
        elif v["kind"] == "evidence_observation_set":
            entry["observations_root_hex"] = v["observations_root_hex"]
        elif v["kind"] == "evidence_empty_tree":
            entry["empty_root_hex"] = v["empty_root_hex"]
        index.append(entry)
    _write_json(os.path.join(TV, "evidence", "index.json"), {"vectors": index})


if __name__ == "__main__":
    gen_serialization()
    gen_assignment()
    gen_reward()
    gen_evidence()
    gen_adversarial()
    print("vectors written to", TV)
