---
name: patterns-to-watch
description: Recurring on-chain issue classes in the Causal Rewards programs to re-check on every review
metadata:
  type: reference
---

# Patterns To Watch (Causal Rewards on-chain)

**How to apply:** run through this list every program review; these are the classes where this
codebase has previously had, or is structurally prone to, bugs.

1. **Recovery/liveness completeness.** For every state that custodies funds or locks bonds, ask:
   is there a reachable instruction that releases those funds/bonds from THIS state? The codebase
   tends to add the happy-path recovery (close from Final) and miss stall/abort paths (see H1).
2. **Multi-instance state transitions.** Counters like `open_challenges` + a status enum: check the
   transition logic for the N>1 case, not just N=1. `resolve_upheld` broke on multiple simultaneous
   challenges (H2). Any "resolve one of many" handler needs the "others still pending" branch.
3. **Spec vs code divergence on transitions.** state-machine.md lists compound transitions
   (e.g. Challenged→Challenged when others pending). Confirm code implements ALL listed branches,
   not just the common one.
4. **Provisional crypto preimages leaking into a hard on-chain dependency.** Reward leaf preimage is
   PROVISIONAL (serialization.md §6.2 deferred) yet settlement claim verification depends on it. Track
   which on-chain verifications depend on not-yet-ratified serialization and flag SDK rework risk.
5. **Caller-supplied amounts not bound to a commitment.** e.g. `total_allocated_base_units` at
   finalize. Confirm the economic guardrail is really the vault balance / Merkle proof, not the
   unchecked scalar.
6. **`init_if_needed` reinit surface.** settlement enables `init-if-needed` for Evaluation resubmit.
   Every field must be overwritten on the reuse path and the status guard must gate reuse.
7. **Window short-circuits.** Boolean OR guards on time windows (`|| ever_challenged`) can collapse a
   protection window; check whether an adversary can trip the cheap side early.
8. **Signature checks pushed off-chain.** Evidence batch signatures are not verified on-chain; confirm
   the verifier/challenge path genuinely covers what the chain skips.
