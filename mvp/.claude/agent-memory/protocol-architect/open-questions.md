---
name: open-questions
description: Remaining open design questions (M2/M3) for the Causal Rewards Protocol spec after M1 serialization ratification
metadata:
  type: project
---

The four M1 open questions are now RESOLVED in-spec (2026-07-17 ratification); see
[[resolved-decisions]]. Remaining open items, all M2/M3 scope:

1. **RESOLVED (2026-07-20).** Evidence artifact is now number-free and serializer-conformant, and the
   evidence leaf sort keys are pinned (serialization.md §6.5). See [[resolved-decisions]]. Done before
   the M1 freeze tag. Nothing left here.

2. **Merkle leaf sort keys — PARTIALLY resolved.** assignment (cohort_id) and evidence (§6.5, three
   trees, by 32-byte key) are PINNED. Still unpinned: **participant** (recommendation: participant id
   asc — pin before first participant golden root, M2) and **reward** (DEFERRED to M3: reward leaf
   identity fields = recipient key + claim binding are reward-compiler output not yet specced;
   reward-policy.md fixes only the amount `leaf_i`). Pin each before its first golden root.

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
