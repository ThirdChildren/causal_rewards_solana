# State Machine

**Spec version:** 1.0.0
**Status:** M1 frozen-READY (awaiting orchestrator freeze gate).

Experiment status: `Draft → Frozen → Active → Evaluating → Challenged → Final → Closed`.
This document is normative for legal transitions, the triggering instruction, guards
(pre-conditions), effects (post-conditions), and the fields that become immutable at `Frozen`.
It maps all **11 instructions** and all **8 accounts** named in CLAUDE.md. There are no dangling
states: every non-terminal state has at least one outgoing transition, and `Closed` is the sole
terminal state.

## 1. Accounts

| Account | Created by | Holds (on-chain, hashes/roots/state only — Invariant 5) |
| --- | --- | --- |
| `ProtocolConfig` | one-time program init | Global config: program authority, hard-zero fee flag, `cluster = devnet` guard, schema version. |
| `Experiment` | `create_experiment` | `status`; `manifest_hash`; coordinator/evaluator pubkeys; `authority_multisig` (threshold + signers); windows; `budget_base_units`; `mint`; `challenge_bond_base_units`; `seed_commitment`; later the `revealed_seed`. |
| `CohortSet` | `publish_cohort_root` | `cohort_root` (assignment/cohort Merkle root); cohort count; bound to `Experiment`. |
| `EvidenceEpoch` | `post_evidence_epoch` (one per epoch) | `epoch_index`; `time_range`; `signer_set_root`; `observations_root`; integer aggregate counts; producer signature ref. |
| `Evaluation` | `submit_evaluation` | `result_artifact_hash`; `reward_root`; `analysis_container_digest` echo; evaluator signature ref. |
| `Challenge` | `open_challenge` (one per challenge) | challenger pubkey; bond amount + escrow state; claim/reason code; `resolution` (unset until resolved). |
| `Distribution` | `finalize_distribution` | finalized `reward_root`; `total_allocated_base_units`; claim window bounds; `unallocated_base_units` (recoverable). |
| `ClaimReceipt` | `claim_reward` (one per claim) | single-use nullifier for a reward leaf; claimed amount; prevents double-claim. |

## 2. Instructions and transitions

Signer column: **C** = coordinator, **E** = evaluator, **M** = multisig (m-of-n), **X** = any
challenger, **P** = participant (leaf owner), **∅** = permissionless/crank. Every state-changing
instruction emits a public event (CLAUDE.md).

| # | Instruction | From → To | Signer | Guards (pre) | Effects (post) |
| --- | --- | --- | --- | --- | --- |
| 1 | `create_experiment` | (none) → `Draft` | C | `ProtocolConfig.cluster == devnet`; fee flag zero; manifest fields well-formed vs `manifest.schema.json`; window ordering `active_start ≤ active_end ≤ evaluation_deadline`, `freeze_by ≥ now`. | Creates `Experiment`; stores draft manifest fields + `seed_commitment`; `status = Draft`. Seed is NOT accepted (no field for it — Invariant 1). |
| 2 | `freeze_experiment` | `Draft` → `Frozen` | M | `status == Draft`; `now ≤ freeze_by`; `manifest_hash` matches canonical hash of the submitted manifest (`serialization.md`); multisig threshold met. | Records `manifest_hash`; locks the immutability set (§3); `status = Frozen`. Freeze precedes any reveal/analysis. |
| 3 | `publish_cohort_root` | `Frozen` → `Active` | C | `status == Frozen`. Seed NOT yet revealed (`revealed_seed` unset). | Creates `CohortSet` with `cohort_root`; `status = Active`. Commits the assignment BEFORE the seed is public, so the seed cannot be chosen to fit a target assignment. |
| 4 | `reveal_seed` | `Active` → `Active` (self-loop) | C | `status == Active`; `CohortSet` exists; `SHA-256(domain_tag‖seed‖salt)` equals the frozen `seed_commitment`; `revealed_seed` unset. | Stores `revealed_seed` + salt. Anyone can now recompute the assignment from the frozen method + seed and check it equals `cohort_root`. |
| 5 | `post_evidence_epoch` | `Active` → `Active` (self-loop) | C | `status == Active`; `now ≤ active_end` (or epoch `time_range` within the active window); `epoch_index` = previous + 1; roots well-formed; batch signature valid. | Creates an `EvidenceEpoch`; anchors signer-set + observations roots and integer counts. Repeatable. |
| 6 | `submit_evaluation` | `Active` → `Evaluating` | E | `status == Active`; `now ≥ active_end`; `revealed_seed` set; at least one `EvidenceEpoch`; echoed `analysis_container_digest` equals the frozen one; `now ≤ evaluation_deadline`. | Creates `Evaluation` with `result_artifact_hash` + `reward_root`; `status = Evaluating`; opens the challenge window (`challenge_window_seconds`). |
| 7 | `open_challenge` | `Evaluating` → `Challenged` | X | `status == Evaluating`; within challenge window; bond ≥ `challenge_bond_base_units` escrowed. | Creates `Challenge`; escrows bond; `status = Challenged`. Multiple challenges may attach; each is its own `Challenge` account. |
| 8 | `resolve_challenge` | `Challenged` → `Evaluating` (upheld-invalid / dismissed) or `Challenged` → `Challenged` (multi-challenge, others pending) | M | `status == Challenged`; multisig threshold; resolution references a verifier outcome. | Sets `Challenge.resolution`. If the challenge is **upheld** (evaluation was non-reproducible/invalid), the `Evaluation` is invalidated and the flow returns to `Evaluating` awaiting a corrected `submit_evaluation`; challenger bond returned. If **dismissed**, bond forfeited. When all challenges resolved and none upheld, state is eligible for finalize. |
| 9 | `finalize_distribution` | `Evaluating` → `Final` (no open challenge) or `Challenged` → `Final` (all resolved, none upheld) | M | Challenge window elapsed OR all challenges resolved with none upheld; a valid `Evaluation` present; multisig threshold. | Creates `Distribution`; locks `reward_root`; records `total_allocated` + `unallocated` (recoverable); `status = Final`; opens claim window (`claim_window_seconds`). |
| 10 | `claim_reward` | `Final` → `Final` (self-loop) | P | `status == Final`; within claim window; Merkle proof of the reward leaf against the finalized `reward_root`; no existing `ClaimReceipt` for that leaf (nullifier unused). | Creates `ClaimReceipt` (single-use nullifier); transfers the leaf amount to the participant. Repeatable across distinct leaves. |
| 11 | `close_experiment` | `Final` → `Closed` | M or ∅ | `status == Final`; claim window elapsed. | Recovers unallocated + unclaimed budget to the funding authority; `status = Closed`. Terminal. |

Notes:
- Self-loops (`reveal_seed`, `post_evidence_epoch`, `claim_reward`) do not change `status`; they
  are listed as transitions because they are gated by it.
- The only way from `Frozen` forward is `publish_cohort_root`; the only path to reveal the seed
  is through `Active`, which is only reachable after `Frozen`. This is the structural encoding of
  freeze-before-reveal (Invariant 1).
- If no challenge is opened, the flow is `Evaluating → Final` directly (transition 9); the
  `Challenged` state is entered only when a challenge exists.

## 3. Immutability frozen at `Frozen`

At `freeze_experiment`, the following become immutable for the life of the experiment. No
instruction — including any multisig path — may alter them (CLAUDE.md: no admin path rewrites
frozen records). Attempting to is a hard error.

- The entire manifest as hashed: `primary_outcome`, `estimand` (unit, cohort/time-block
  definitions, effect definition), `design` (template + strong-claim eligibility + parameters),
  `treatment` (method + treated fraction), `assignment.seed_commitment`, the full `analysis_plan`
  (estimator, SE method, sidedness, `confidence_level_micro`, `critical_value_micro`,
  `minimum_sample`, `analysis_container_digest`), the full `reward_policy` (budget, mint,
  transform, `reward_curve`, `reward_curve_hash`, `intra_cohort_split`, overflow/unused policies),
  `windows`, and `authorities`.
- Consequently: the assignment method and seed commitment cannot change (so the later revealed
  seed is bound); the estimator/container cannot change (so the result is reproducible); the
  reward curve and split cannot change (so payouts are pre-committed).

What is written *after* freeze but is itself append-only / write-once: `cohort_root`
(`publish_cohort_root`), `revealed_seed` (`reveal_seed`, once), each `EvidenceEpoch`,
the `Evaluation` (replaceable only via an upheld challenge), the `Distribution`, and each
`ClaimReceipt` (write-once nullifier).

## 4. State coverage check

| State | Reachable via | Outgoing |
| --- | --- | --- |
| `Draft` | `create_experiment` | `freeze_experiment` |
| `Frozen` | `freeze_experiment` | `publish_cohort_root` |
| `Active` | `publish_cohort_root` | `reveal_seed`, `post_evidence_epoch` (self), `submit_evaluation` |
| `Evaluating` | `submit_evaluation`, resolved-upheld `resolve_challenge` | `open_challenge`, `finalize_distribution` |
| `Challenged` | `open_challenge` | `resolve_challenge`, `finalize_distribution` |
| `Final` | `finalize_distribution` | `claim_reward` (self), `close_experiment` |
| `Closed` | `close_experiment` | terminal |

No state other than `Closed` lacks an outgoing transition; every state is reachable from
`Draft`. All 11 instructions and all 8 accounts appear above.
