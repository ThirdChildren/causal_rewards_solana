---
name: state-machine-v1-1-settlement-hardening
description: state-machine.md v1.1.0 settlement-flow decisions — tx9 guard fix (M1), tx8 multi-challenge (H2), abort_experiment (H1), M3 advisory accounting; wire/hash contract still 1.0.0
metadata:
  type: project
---

`state-machine.md` bumped to **protocol-behavior version 1.1.0** while the **wire/hash contract stays
1.0.0** (two-track versioning, documented in the new §5 Revision history). No manifest field, schema,
`serialization.md` byte, or golden hash changed; manifest `spec_version` stays `"1.0.0"`. Behavior-only,
additive. Golden hashes untouched: manifest `74e0bb82…`, `reward_curve_hash` `14b0ec34…`, evidence
example `901b08d5…`. See [[spec-invariants-and-conventions]].

**Closed M2 security findings (feed straight to solana-program-engineer):**

- **M1 — tx9 `finalize_distribution` guard.** OLD racy rule `now ≥ challenge_window_end OR
  ever_challenged` replaced with the conjunction **`now ≥ challenge_window_end AND open_challenges == 0`**.
  `ever_challenged` is REMOVED from the protocol entirely — no longer a field, no short-circuit. Finalize
  is now taken only from `Evaluating`. `challenge_window_end` is an absolute unix ts written once at tx6.
- **H2 — tx8 `resolve_challenge`.** `open_challenges` (u32 on Experiment) is the sole gate for leaving
  `Challenged`. Each resolve handles one Challenge, releases exactly that bond (upheld→returned to
  challenger, dismissed→forfeited to coordinator) order-independently, decrements the counter. Any upheld
  sets `evaluation_valid=false` (evaluation must be re-submitted via tx6 self-loop). State returns to
  `Evaluating` only when counter hits 0.
- **H1 — tx12 `abort_experiment` (NEW 12th instruction).** From any pre-`Final` state
  (Frozen/Active/Evaluating/Challenged) → `Closed` with `aborted=true` marker (reuses Closed, NO 8th
  status word). Guard: multisig OR permissionless timeout `now > evaluation_deadline +
  ProtocolConfig.abort_grace_seconds`. Returns vault to `experiment.coordinator`; refunds all still-open
  challenge bonds to challengers (un-adjudicated → returned, never forfeited); cannot run once any claim
  occurred (structurally guaranteed since abort is pre-Final; asserted defensively as "no Distribution/
  ClaimReceipt exists").

**New Experiment account fields:** `challenge_window_end`, `open_challenges`, `evaluation_valid`,
`aborted`. **New ProtocolConfig field:** `abort_grace_seconds`. tx6 now also self-loops
`Evaluating→Evaluating` for corrected re-submission after an upheld challenge.

**M2 re-review Warnings W1/W2 — DISCLOSED, DEFERRED to M4** (doc-only, no behavior/schema/hash change,
2026-07). Added `threat-model.md` §5 "Deferred hardening items (tracked for M4)" + a W2 inverse row in
§3.4 + a one-line pointer in `state-machine.md` §5 (v1.1.0). Both accepted for devnet zero-value MVP
(Invariant 7), MUST fix before real-value deployment:
- **W2** — tx8 dismissed-challenge bond forfeits to `experiment.coordinator`; multisig-gated resolution +
  coordinator alignment = incentive to dismiss VALID challenges to capture bonds. On-chain control: none
  beyond off-chain verifier detectability. M4 fix: route bond to neutral sink (burn or non-coordinator
  config treasury).
- **W1** — tx12 permissionless timeout-abort (`evaluation_deadline + abort_grace_seconds`) can discard a
  valid ready-to-finalize evaluation from `Evaluating` because tx1 does NOT enforce
  `abort_grace_seconds > challenge_window_seconds`. Liveness inversion, no theft. M4 fix: enforce that
  inequality at create, and/or reject timeout-abort when `status==Evaluating && evaluation_valid`.

**M3 (advisory accounting)** documented in `reward-policy.md` new section "Advisory on-chain accounting":
`Distribution.total_allocated_base_units` is an advisory ≤-budget bound, NOT cryptographically bound to
`Σ leaf_i`. Real guardrails: per-claim Merkle-proof ceiling + verifier/challenge reproduction
(Invariant 6). Cross-referenced from tx9 and §5. Distinct from the M3 reward-leaf-index residual in
[[reward-leaf-ratification]] (that M3 is the leaf_index tie-break; this M3 is the accounting note — same
finding label, different topic).
