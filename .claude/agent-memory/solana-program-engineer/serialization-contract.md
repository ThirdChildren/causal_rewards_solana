---
name: serialization-contract
description: Byte-level hashing/Merkle/seed-commit rules the on-chain code MUST match, sourced from serialization.md (RATIFIED) + verifier reference
metadata:
  type: reference
---

# Canonical serialization contract (on-chain MUST match)

Authoritative: `mvp/causal-rewards/specs/serialization.md` (RATIFIED, spec-v1-frozen).
Conformance oracle: `mvp/causal-rewards/verifier-cli/reference/` (`canonical.py`, `merkle.py`, `assignment.py`).
Golden vectors: `mvp/causal-rewards/test-vectors/`. **Do NOT introduce a second encoder.**

- Hash: **SHA-256** only. `H(x)=sha256(x)`.
- Merkle (all trees): `leaf_hash = sha256(0x00 || DOMAIN_TAG || leaf_bytes)`, `node_hash = sha256(0x01 || left || right)`. Odd trailing node is **PROMOTED unchanged** (NOT duplicated — CVE-2012-2459). Empty tree root = **32 zero bytes**.
- Domain tags (ASCII): participant=`CRP:participant:v1`, assignment=`CRP:assignment:v1`, evidence=`CRP:evidence:v1`, reward=`CRP:reward:v1`. Evidence sub-commitments: signer leaf domain `signer`, obs leaf domain `obs` (inside the 0x00 leaf preimage).
- Seed commitment (NO salt): `SEED_COMMIT_DOMAIN=b"CRP-seed-commit-v1"`; `seed_commitment = sha256(SEED_COMMIT_DOMAIN || seed)`, seed is raw **32 bytes**. `reveal_seed` recomputes this and rejects if != stored commitment. NOTE: state-machine.md row 4 mentions a `salt` — that is superseded by serialization.md §7.2 (no salt); see [[spec-open-items]].
- Assignment PRF (off-chain; not needed on-chain): `sha256(b"CRP-assign-v1" || seed(32) || u32be(len id)||id || u32be(len cohort)||cohort)`, prf_u64 = first 8 bytes big-endian. bernoulli: treatment iff prf_u64 % 1_000_000 < treat_fraction_ppm. fixed_count: sort by (prf_u64, cohort_id) asc, first k treated. Leaf = CJSON `{"arm":..,"cohort_id":..}`.
- Verified golden values (from `test-vectors/assignment/index.json`, reproduced in crp-crypto host tests): assign-01 root=`c229b5ccfdf447900526a45afac31a009c6348685b135edfe2eb6139ef1b914d`, seed_commit(all-zero seed)=`f2261eaa83213f94c8002ebf49daee8045fd34caa803c3d53b1d0aeb0fe6cd9c`.
- Manifest golden hash = `74e0bb825013fcd4a2327b234a5f44c48cd709e7a3025cd30a3b26ace68f81b2` (what experiment-registry stores as frozen manifest hash). Reproduce: `python3 -c "import json,canonical;print(canonical.sha256_hex(canonical.canonical_json_bytes(json.load(open('specs/examples/manifest.example.json')))))"` in verifier-cli/reference.

Numbers in hashed artifacts are decimal STRINGS (no JSON number tokens); on-chain we store the integers themselves (u64/i64) and never re-serialize a manifest on-chain — we store the manifest_hash computed off-chain.
