---
name: sim-determinism-and-serialization
description: How the simulator achieves determinism and why its content hash must follow specs/serialization.md (float-free, integer-scaled)
metadata:
  type: project
---

The `simulator/` (package `depin_sim`) content hash MUST conform to `specs/serialization.md`
(owned by protocol-architect): **no floating-point in hashed bytes**, every real value
integer-scaled at micro (1e-6) with round-half-to-even, keys sorted by code point, SHA-256 hex.
Enforced solely in `src/depin_sim/canonical.py`.

**Why:** serialization.md §1.2 forbids floats in any hashed protocol artifact to make float
formatting / locale / rounding drift structurally impossible. The simulator reuses the SAME
rule so one canonical serializer covers both the sim hash and the on-chain manifest/reward roots.
serialization.md §3 (RATIFIED) is still PENDING — golden hashes are provisional until then.

**How to apply:** if §3 diverges from the provisional CJSON, reconcile in `canonical.py` ONLY and
regenerate any committed golden hash in the same change. Do not add a hard-coded golden-hash test
until §3 is ratified. Determinism is proven instead by same-seed→same-hash reruns
(`tests/test_determinism.py`, `make determinism`).

Other determinism load-bearing choices: single committed seed → numpy `SeedSequence` spawning with
a fixed append-only stream order (`seeds.py`, a contract — never reorder); numpy PCG64 only in the
DGP (BLAS-independent, no scipy sampling/matmul); treatment assignment isolated behind
`assignment.py::assign` so it can be swapped for the canonical seed→assignment rule from
`verifier-reproducibility-engineer` without touching the pipeline. Provisional baseline_alpha
content hash (alpha env, numpy 2.1.3): `31135b85f4c18e4022b58f7d0dbfa1ef018990b29990b331a0048104e165dc67`.

See [[scenario-power-findings]].
