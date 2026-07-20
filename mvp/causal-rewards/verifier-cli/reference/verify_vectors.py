"""Independent re-derivation check for the golden vectors (acceptance test).

Loads each published vector file, recomputes every canonical byte string, hash,
and root purely from the vector's declared INPUTS, and asserts each recomputed
value equals the stored expected value. Exits non-zero on any divergence,
reporting the first point of divergence.

Run:  python3 verify_vectors.py
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from canonical import canonical_json_bytes, sha256_hex
from merkle import DOMAIN_ASSIGNMENT, DOMAIN_EVIDENCE, leaf_hash, merkle_root
from assignment import (
    assignment_leaf_bytes,
    cohort_prf,
    derive_assignment,
    seed_commitment,
)

HERE = os.path.dirname(os.path.abspath(__file__))
TV = os.path.abspath(os.path.join(HERE, "..", "..", "test-vectors"))

_failures = []


def check(label: str, got: Any, want: Any) -> None:
    if got != want:
        _failures.append((label, got, want))


def verify_serialization() -> None:
    d = os.path.join(TV, "serialization")
    for fn in sorted(os.listdir(d)):
        if fn == "index.json" or not fn.endswith(".json"):
            continue
        rec = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        cb = canonical_json_bytes(rec["input"])
        check(f"{rec['name']}: canonical_bytes_hex", cb.hex(), rec["canonical_bytes_hex"])
        check(f"{rec['name']}: canonical_length", str(len(cb)), rec["canonical_length"])
        check(f"{rec['name']}: sha256_hex", sha256_hex(cb), rec["sha256_hex"])


def verify_assignment() -> None:
    d = os.path.join(TV, "assignment")
    for name in sorted(os.listdir(d)):
        vp = os.path.join(d, name, "vector.json")
        if not os.path.isfile(vp):
            continue
        rec = json.load(open(vp, encoding="utf-8"))
        inp = rec["inputs"]
        seed = bytes.fromhex(inp["seed_hex"])
        exp = inp["experiment_id"]

        check(
            f"{name}: seed_commitment",
            seed_commitment(seed).hex(),
            rec["step1_seed_commitment"]["seed_commitment_hex"],
        )

        want_prf = {v["cohort_id"]: v["prf_u64"] for v in rec["step2_cohort_prf"]["values"]}
        for cid in inp["cohort_ids"]:
            check(f"{name}: prf[{cid}]", str(cohort_prf(seed, exp, cid)), want_prf[cid])

        assigns = derive_assignment(seed, exp, inp["cohort_ids"], inp["design"], inp["params"])
        want_leaves = {l["cohort_id"]: l for l in rec["step4_leaves"]["leaves"]}
        leaf_bytes_list = []
        for a in assigns:
            lb = assignment_leaf_bytes(a)
            leaf_bytes_list.append(lb)
            wl = want_leaves[a.cohort_id]
            check(f"{name}: {a.cohort_id} arm", a.arm, wl["arm"])
            check(f"{name}: {a.cohort_id} leaf_bytes", lb.hex(), wl["leaf_canonical_bytes_hex"])
            check(
                f"{name}: {a.cohort_id} leaf_hash",
                leaf_hash(DOMAIN_ASSIGNMENT, lb).hex(),
                wl["leaf_hash_hex"],
            )

        want_root = rec["step5_assignment_root"]["assignment_root_hex"]
        check(
            f"{name}: assignment_root",
            merkle_root(leaf_bytes_list, DOMAIN_ASSIGNMENT).hex(),
            want_root,
        )

        # Determinism: the root MUST NOT depend on input cohort order. Re-derive
        # from the reversed input list and assert the identical root.
        assigns_rev = derive_assignment(
            seed, exp, list(reversed(inp["cohort_ids"])), inp["design"], inp["params"]
        )
        root_rev = merkle_root(
            [assignment_leaf_bytes(a) for a in assigns_rev], DOMAIN_ASSIGNMENT
        ).hex()
        check(f"{name}: assignment_root invariant under input order", root_rev, want_root)


def verify_adversarial() -> None:
    """Re-evaluate each adversarial fixture's rejection predicate.

    For each negative fixture we PROVE the input really is rejectable: the check
    predicate must hold. A fixture that fails to be rejectable (e.g. a claimed
    seed mismatch whose commitment actually matches) is itself a bug and fails.
    """
    d = os.path.join(TV, "adversarial")
    if not os.path.isdir(d):
        return
    for fn in sorted(os.listdir(d)):
        if fn == "index.json" or not fn.endswith(".json"):
            continue
        rec = json.load(open(os.path.join(d, fn), encoding="utf-8"))
        name = rec["name"]
        inp = rec["inputs"]
        check(f"{name}: expected_result is reject", rec["expected_result"], "reject")
        kind = rec["check"]["kind"]

        if kind == "seed_commitment_mismatch":
            got = seed_commitment(bytes.fromhex(inp["revealed_seed_hex"])).hex()
            check(
                f"{name}: recomputed commitment of revealed seed",
                got,
                rec["expected"]["recomputed_commitment_of_revealed_seed_hex"],
            )
            # Rejection holds iff the revealed seed does NOT open the frozen commitment.
            check(
                f"{name}: rejection holds (commitment != frozen)",
                got != inp["frozen_seed_commitment_hex"],
                True,
            )
        elif kind == "epoch_index_not_monotonic":
            required = str(int(inp["previous_epoch_index"]) + 1)
            check(
                f"{name}: required next epoch_index",
                required,
                rec["expected"]["required_next_epoch_index"],
            )
            check(
                f"{name}: rejection holds (attempted != required next)",
                inp["attempted_epoch_index"] != required,
                True,
            )
        elif kind == "duplicate_evidence_leaf":
            la = leaf_hash(DOMAIN_EVIDENCE, canonical_json_bytes(inp["batch_a"])).hex()
            lb = leaf_hash(DOMAIN_EVIDENCE, canonical_json_bytes(inp["batch_b"])).hex()
            check(f"{name}: batch_a leaf_hash", la, rec["expected"]["batch_a_leaf_hash_hex"])
            check(f"{name}: batch_b leaf_hash", lb, rec["expected"]["batch_b_leaf_hash_hex"])
            check(f"{name}: rejection holds (leaves are duplicate)", la == lb, True)
        elif kind == "stale_evaluation_state_mismatch":
            check(
                f"{name}: rejection holds (referenced root != committed root)",
                inp["evaluation_referenced_cohort_root_hex"]
                != inp["committed_cohort_root_hex"],
                True,
            )
        elif kind == "container_digest_mismatch":
            check(
                f"{name}: rejection holds (echoed digest != frozen digest)",
                inp["echoed_analysis_container_digest"]
                != inp["frozen_analysis_container_digest"],
                True,
            )
        elif kind == "double_claim_nullifier_reuse":
            check(
                f"{name}: rejection holds (second claim re-uses the nullifier)",
                inp["first_claim"]["nullifier_hex"] == inp["second_claim"]["nullifier_hex"],
                True,
            )
        else:
            _failures.append((f"{name}: unknown check kind", kind, "a known check kind"))


def main() -> int:
    verify_serialization()
    verify_assignment()
    verify_adversarial()
    if _failures:
        print("DIVERGENCE (first %d shown):" % min(len(_failures), 10))
        for label, got, want in _failures[:10]:
            print(f"  {label}\n     got : {got}\n     want: {want}")
        return 1
    print(
        "OK: all serialization + assignment vectors re-derived and match; "
        "all adversarial fixtures confirmed rejectable."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
