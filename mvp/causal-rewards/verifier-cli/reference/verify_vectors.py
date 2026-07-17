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
from merkle import DOMAIN_ASSIGNMENT, leaf_hash, merkle_root
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

        check(
            f"{name}: assignment_root",
            merkle_root(leaf_bytes_list, DOMAIN_ASSIGNMENT).hex(),
            rec["step5_assignment_root"]["assignment_root_hex"],
        )


def main() -> int:
    verify_serialization()
    verify_assignment()
    if _failures:
        print("DIVERGENCE (first %d shown):" % min(len(_failures), 10))
        for label, got, want in _failures[:10]:
            print(f"  {label}\n     got : {got}\n     want: {want}")
        return 1
    print("OK: all serialization and assignment vectors re-derived and match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
