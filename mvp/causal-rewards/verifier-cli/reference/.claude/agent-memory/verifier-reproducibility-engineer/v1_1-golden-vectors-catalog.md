---
name: v1_1-golden-vectors-catalog
description: Ratified reference roots for the v1.1 golden vectors I produced — reward (§6.6), switchback + matched_cluster assignment (§7.4), evidence (§6.5) — plus the canonical rules each pins
metadata:
  type: project
---

The v1.1 residual-closure golden vectors I produced (2026-07-23) from `specs/serialization.md`
1.1.0 + the reference impl (`verifier-cli/reference/`). All byte-stable across 2 runs;
`verify_vectors.py` re-derives every one from inputs (exit 0). These roots are RATIFIED reference
values (recorded by the orchestrator in CONTEXT_HANDOFF.txt). New reference modules added:
`reward.py`, `evidence.py`; `assignment.py` extended with switchback + matched_cluster + the
composite `group"|"index` grammar + integer round-half-to-even. All stdlib-only (base58 hand-rolled).

**REWARD (§6.6 aggregate-one-leaf-per-recipient).** Leaf = raw 48B `recipient(32) ||
amount_u64_BE(8) || leaf_index_u64_BE(8)`, hashed `SHA-256(0x00 || "CRP:reward:v1" || content)`.
Σ over cohorts per recipient, DROP zero-sum, rank by recipient BE32 (unique key) then amount,
leaf_index = 0-based rank. Roots (`test-vectors/reward/`):
- reward-01-multi-recipient-ordering: `a9c35cf41603d593c123e962f41fc47a2d750cf1e536b177f2454ace647fc171`
- reward-02-zero-sum-dropped: `ea9431826b81982577d70ea8ac6159aa8b600a77889c45c84b2ff5afc8ae0ffc`
- reward-03-single-recipient: `b882c8992309c1269d9e9d6b887faeb2c2361ea112d5c495fe00c520d8655ced`
- reward-05-empty-all-zero: `00…00` (32 zero bytes, §6.4)
- reward-04-duplicate-recipient-error: HARD ERROR `DUPLICATE_REWARD_RECIPIENT` (recipient unique key)

**ASSIGNMENT switchback + matched_cluster (§7.4).** Leaf/ordering unchanged from the existing 11:
leaf = `{arm, cohort_id}` CJSON, sorted by FULL composite `cohort_id`, DOMAIN `CRP:assignment:v1`.
switchback: `phase(group)=prf(group)&1`, `arm=treatment iff (index+phase)%2==1`,
`treated_fraction_micro` MUST be `"500000"` (asserted, not read). matched_cluster:
`k_s=round_half_even(frac·m_s/1e6)` clamped [0,m_s], rank by `(prf(full id), member_index)`.
Roots (`test-vectors/assignment/`):
- assign-12-switchback-2geo-2period: `c7a4253f78ed98de6db3c05ad95cf0736ba610c121bd64622c65deb3770e08a8`
- assign-13-switchback-3geo-noncontiguous: `35f6a7f62061c9e2163a0056286984820d0f00790431c9fee0d45db8c235787c`
- assign-14-matched-pairs-2x2 (m_s=2,frac=500000→k_s=1): `e67ebfe91bdc574095b2c54aa15e03b2320eb22fae638472e52e55b35ab8fdc1`
- assign-15-matched-mixed-strata-halfeven (m_s=3,frac=500000→k_s=2 banker's-round tie; m_s=2→k_s=1): `a1116ebf57794629d2d983ef0677a6341949f8a9717e4e4f6c368a6cf5d380a0`
Existing 11 assign roots + manifest `74e0bb82…` unchanged (v1.1 additive/hash-compatible, confirmed).

**EVIDENCE off-chain (§6.5), see [[evidence-serialization-pinning]].** Roots (`test-vectors/evidence/`):
- evidence-01-epoch-multibatch (leaf=CJSON(batch), sort by leaf_hash): `a13e1cdc8702252b89ab08b6943ae82bc65325c2bbce119211a270abc87deeb2`
- evidence-02-signer-set-multisigner (domain 'signer', sort by be32): `e45697c86d48d63b8c25a975224344060a4b5cf72bd7d00b3364b6247e5fd52e`
- evidence-03-observation-set (domain 'obs', sort by be32): `1010891bf501f89b96db447a295d0820c20ad694afdcff4cf5c0c2e368ebaf56`
- evidence-04-empty-tree: `00…00` (32 zero bytes)
- evidence-05-signer-not-32-error: HARD ERROR `SIGNER_PUBKEY_NOT_32_BYTES`

**SIM non-ASCII parity (carried discrepancy #2) VERIFIED PASS (independent own fixture).**
`simulator/src/depin_sim/canonical.py` == `verifier-cli/reference/canonical.py` byte-for-byte on
non-ASCII (decomposed vs precomposed NFC, non-ASCII keys/values, UTF-16 vs code-point ordering
discriminator via astral U+1F9EA vs BMP fullwidth key, duplicate-key-after-NFC hard error). The two
diverge ONLY on bare number tokens (sim carries integer-scaled ints; reference forbids all number
tokens), which is the documented single-point deliberate divergence — never triggered on the shared
number-free domain. The sim's own committed oracle `tests/test_canonical.py` (27 tests) also green.
NOTE: numpy + pytest were NOT preinstalled here; needed `pip install --break-system-packages`.
