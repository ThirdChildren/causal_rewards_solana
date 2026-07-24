---
name: cross-impl-matrix
description: Which root/primitive agrees across Python verifier, TS SDK, and on-chain crp-crypto — empirically confirmed 2026-07-24
metadata:
  type: project
---

Empirically re-derived 2026-07-24 (node 24 + `sdk/typescript/dist/`, Python reference,
crp-crypto source at `crates/crp-crypto/src/lib.rs`).

**3-way byte-identical (Py verifier == TS SDK == on-chain crp-crypto):**
- assignment leaf + assignment_root (assign-01 → `c229b5cc…`, TS re-derived match)
- seed_commitment, cohort_prf, derive_assignment bernoulli + fixed_count
- reward leaf hash §6.6 + reward_root (reward-01 → `a9c35cf4…`, TS re-derived match)
- merkle_root / merkle_root_from_hashes / leaf_hash / node_hash primitives

**Py + TS only (on-chain N/A — chain never serializes JSON):**
- manifest_hash = SHA-256(CJSON), result_artifact_hash = SHA-256(CJSON(analysis))
  (TS via canonicalJsonBytes+sha256; chain anchors/compares the hash, doesn't canonicalize)
- evidence epoch root (evidence-01 → `a13e1cdc…`): TS reproduces via
  canonicalJsonBytes(batch)+leaf_hash+merkleRootFromHashes — matches Python.
- derive_assignment switchback + matched_cluster (on-chain has only bernoulli+fixed_count)

**Python-only (off-chain, no TS/on-chain equivalent):**
- evidence signer_subtree (`e45697c8…`) + observation_subtree (`1010891b…`) — off-chain
  sub-commitments; TS crypto module does not expose them (M4 candidate if needed).

TS `deriveAssignment` takes a design OBJECT `{kind:'bernoulli',treatFractionPpm}` /
`{kind:'fixed_count',treatmentCount}` — NOT (designStr, params) like Python. RewardLeaf.recipient
is a web3.js `PublicKey`.
