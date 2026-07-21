---
name: spec-open-items
description: Points where the frozen spec is silent, deferred, or internally inconsistent and must be resolved by protocol-architect before golden roots/mainnet
metadata:
  type: project
---

# Spec open items affecting the on-chain programs

Raised to orchestrator/protocol-architect during M2. Do NOT silently work around — these are flagged.

1. **Seed-commit salt inconsistency.** `state-machine.md` row 4 says `reveal_seed` checks `SHA-256(domain_tag‖seed‖salt)`; `serialization.md` §7.2 (RATIFIED) says NO salt: `sha256("CRP-seed-commit-v1"||seed)`. serialization.md wins (it is the ratified byte-level authority and matches the verifier reference + golden vectors). **Implemented per serialization.md (no salt).** Recommend protocol-architect delete the `‖salt` mention from state-machine.md.
   **Why:** determinism/reproducibility (Invariant 2) is anchored on the verifier reference, which has no salt.

2. **RESOLVED — reward Merkle leaf preimage is RATIFIED in serialization.md §6.6** (unchanged from the M2 provisional layout): `reward_leaf_content = recipient(32) || amount_base_units(u64 BE) || leaf_index(u64 BE)` (48 bytes), `leaf_hash = sha256(0x00 || "CRP:reward:v1" || content)`. §6.6 also resolves the §6.2 reward-ordering deferral: leaf tree position == `leaf_index`, contiguous from 0 (duplicate/gap = hard error, empty tree root = 32 zero bytes). `crp-crypto` `reward_leaf_content`/`reward_leaf_hash` and `settlement::claim_reward` are unchanged and now match the ratified spec; the doc comment in `crp-crypto/src/lib.rs` cites §6.6. **RESIDUAL (M3, off-chain only):** the `leaf_index` tie-break sub-key when `(recipient, amount)` isn't unique is a reward-compiler decision (`reward-policy.md`) — does NOT affect the on-chain leaf preimage.

3. **switchback / matched-cluster assignment derivations** unpinned in §7.4 (open M2 item, joint with causal-inference-engineer). Not needed on-chain (assignment derivation is off-chain; on-chain only checks seed commitment + stores cohort_root), so it does not block M2 programs.
