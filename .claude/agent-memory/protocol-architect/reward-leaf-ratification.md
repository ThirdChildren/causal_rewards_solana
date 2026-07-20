---
name: reward-leaf-ratification
description: serialization.md §6.6 ratifies the reward Merkle leaf preimage + ordering; records the one M3 residual and the experiment_id-binding decision
metadata:
  type: project
---

The reward Merkle leaf was promoted from DEFERRED (old §6.2 bullet) to RATIFIED in
`serialization.md` §6.6 (new subsection, mirrors §6.5 evidence structure). Spec version still 1.0.0.

**Ratified leaf (unchanged from the settlement program's provisional layout):**
`leaf_hash = SHA-256( 0x00 || "CRP:reward:v1" || recipient(32 raw) || amount_base_units(u64 BE) || leaf_index(u64 BE) )`
— fixed 48-byte content, 62-byte preimage. Raw-byte leaf, NOT CJSON (§2/§3 don't apply, like the
§6.5 obs/signer leaves).

**Decision — experiment_id binding: NO.** Follows the §7.5 assignment-leaf precedent. reward_root is
per-experiment (Distribution PDA), claim verifies proof against that root, nullifier is per-experiment
→ cross-experiment replay is structurally impossible without adding 32 bytes/leaf. Reasoning written
into §6.6.

**Ordering:** leaves by `leaf_index` ascending, contiguous 0..N-1 (position == leaf_index). Duplicate
or gapped leaf_index = hard error. Empty tree = 32 zero bytes.

**THE ONE OPEN RESIDUAL (M3, owned by reward-policy.md + reward compiler):** the tie-break used to
*assign* leaf_index when `(recipient, amount_base_units)` is not unique — equivalently, whether the
compiler emits one aggregated leaf per recipient or one leaf per (recipient × cohort). Primary rank
key `(recipient BE, amount)` is already pinned. MUST be fixed in reward-policy.md and pinned in §6.6
before the first reward golden root is committed. See [[spec-invariants-and-conventions]].

**Endianness footgun documented:** leaf preimage uses BE for amount+leaf_index; ClaimReceipt nullifier
PDA seed uses `leaf_index.to_le_bytes()` (LE). Intentionally different; §6.6 warns not to harmonize.

**Stale code comment to clean up (not touched — out of scope):** `crates/crp-crypto/src/lib.rs`
still labels `reward_leaf_content`/`reward_leaf_hash` "PROVISIONAL M2 ... §6.2 defers this". Now
ratified as-is, so no code change to logic — only the comment is stale. Flag to orchestrator/
solana-program-engineer.

Untouched (verified): manifest golden `74e0bb82...`, evidence example CJSON `901b08d5...`. Only
serialization.md and reward-policy.md (prose) were edited.
