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

2. **Reward Merkle leaf preimage is DEFERRED in spec §6.2** (reward tree sort key + leaf identity fields "MUST be pinned before the first reward golden root, M3"). `reward-policy.md` fixes only the leaf *amount*. To implement `claim_reward` in M2 I used a **PROVISIONAL** fixed-width reward leaf: `leaf_content = recipient_pubkey(32 BE) || amount_base_units(u64 BE) || leaf_index(u64 BE)`, `leaf_hash = sha256(0x00 || "CRP:reward:v1" || leaf_content)`. This is spec-consistent in *style* (§6.5 allows fixed-width raw-byte leaves + the reward domain tag) but the exact layout is NOT yet ratified. **MUST be ratified in serialization.md §6.2 before any reward golden root or the SDK freezes claim encoding.** Flagged to orchestrator.
   **Why:** claim_reward needs a concrete leaf to verify Merkle proofs against; there is no ratified one yet.

3. **switchback / matched-cluster assignment derivations** unpinned in §7.4 (open M2 item, joint with causal-inference-engineer). Not needed on-chain (assignment derivation is off-chain; on-chain only checks seed commitment + stores cohort_root), so it does not block M2 programs.
