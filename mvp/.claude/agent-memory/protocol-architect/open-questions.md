---
name: open-questions
description: Remaining open design questions (M2/M3) for the Causal Rewards Protocol spec after M1 serialization ratification
metadata:
  type: project
---

The four M1 open questions are now RESOLVED in-spec (2026-07-17 ratification); see
[[resolved-decisions]]. Remaining open items, all M2/M3 scope:

1. **Evidence artifact is NOT yet number-free.** `evidence.schema.json` + `examples/evidence.example.json`
   still use JSON integer tokens (epoch_index, time_range, signer_count, leaf_count, aggregate_summary
   counts). The ratified serializer (`serialization.md` §2) FORBIDS number tokens in any hashed
   artifact and the verifier reference RAISES on ints — so evidence cannot currently be canonicalized.
   **Why:** deferred deliberately — no evidence golden root exists yet, and the evidence Merkle-tree
   leaf sort key is itself still `[RATIFY]` (serialization.md §6.2), both M3 scope.
   **How to apply:** when evidence roots land (M3), migrate every evidence numeric field to canonical
   integer-scaled strings (same regexes as manifest) and pin the evidence leaf sort key in
   serialization.md §6.2 IN THE SAME change. Flagged to orchestrator during M1 ratification.

2. **Merkle leaf sort keys for participant/evidence/reward trees** are unpinned (serialization.md
   §6.2). Only the assignment tree (sort by cohort_id) is fixed. Must be pinned before each tree's
   first golden root is committed (M2 participant/assignment done; evidence/reward M3).

3. **Switchback & matched-cluster ASSIGNMENT DERIVATION rules** are unpinned (serialization.md §7.4).
   Only bernoulli + fixed_count PRF derivations exist. Needed before an M2 switchback assignment root.
   NOTE: this is distinct from switchback DESIGN parameters (carryover/washout/interference), which
   ARE now frozen in the manifest schema (resolved).

4. **Simulator canonical.py latent divergence from ratified rules** (do not edit their code; reported
   to orchestrator). `simulator/src/depin_sim/canonical.py` uses `json.dumps(ensure_ascii=True,
   sort_keys=True)` and does NOT NFC-normalize. Diverges from serialization.md for NON-ASCII content:
   (a) ensure_ascii escapes non-ASCII to `\uXXXX` vs the spec's raw UTF-8 (§4); (b) no NFC (§3.5);
   (c) code-point vs UTF-16 key order (moot with ASCII keys). Identical for ASCII-only payloads, so
   harmless today, but a real spec deviation to reconcile before the simulator emits a cross-checked
   golden hash against manifest/reward roots.

See [[spec-versions]] and [[resolved-decisions]].
