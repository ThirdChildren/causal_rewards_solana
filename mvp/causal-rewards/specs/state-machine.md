# State Machine

**State-machine / protocol-behavior version:** 1.1.0
**Wire/hash contract version:** 1.1.0 — advanced from 1.0.0 by an **additive, hash-compatible** minor
revision in `serialization.md` v1.1 (residuals A/B/C: reward `leaf_index` assignment, switchback +
matched_cluster derivations, evidence-sort-key confirmation). The manifest schema & example, the
evidence schema & example, the manifest `spec_version` field `"1.0.0"`, and every golden hash
(manifest `74e0bb82…`, `reward_curve_hash` `14b0ec34…`, evidence example `901b08d5…`) are
byte-identical to v1.0. A v1.0.0 manifest is valid under v1.1 and hashes identically. This document's
behavior text below is unchanged from state-machine v1.1.0.
**Status:** M1 frozen-READY. v1.1 is a minor, additive, hash-compatible revision: it adds one
on-chain instruction (`abort_experiment`) and tightens transitions 6, 8, and 9 to close the M2
security findings (M1 challenge-window short-circuit, H1 pre-`Final` fund trap, H2 multi-challenge
resolution). No hashed artifact and no manifest field changes. See the Revision history (§5).

Experiment status: `Draft → Frozen → Active → Evaluating → Challenged → Final → Closed`.
This document is normative for legal transitions, the triggering instruction, guards
(pre-conditions), effects (post-conditions), and the fields that become immutable at `Frozen`.
It maps all **12 instructions** (the 11 core instructions in CLAUDE.md plus `abort_experiment`,
added in state-machine v1.1) and all **8 accounts** named in CLAUDE.md. There are no dangling
states: every non-terminal state has at least one outgoing transition, and `Closed` is the sole
terminal state.

## 1. Accounts

| Account | Created by | Holds (on-chain, hashes/roots/state only — Invariant 5) |
| --- | --- | --- |
| `ProtocolConfig` | one-time program init | Global config: program authority, hard-zero fee flag, `cluster = devnet` guard, schema version, `abort_grace_seconds` (timeout offset for the permissionless abort path, §2 tx12). |
| `Experiment` | `create_experiment` | `status`; `manifest_hash`; coordinator/evaluator pubkeys; `authority_multisig` (threshold + signers); windows; `budget_base_units`; `mint`; `challenge_bond_base_units`; `seed_commitment`; later the `revealed_seed`; and the mutable settlement-flow counters set after evaluation: `challenge_window_end` (absolute unix ts, set at `submit_evaluation`), `open_challenges` (u32 count of unresolved `Challenge` accounts), `evaluation_valid` (bool; `false` after an upheld challenge until a corrected `submit_evaluation`), `aborted` (bool marker set only by `abort_experiment`). |
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
| 4 | `reveal_seed` | `Active` → `Active` (self-loop) | C | `status == Active`; `CohortSet` exists; `SHA-256(SEED_COMMIT_DOMAIN‖seed)` equals the frozen `seed_commitment` (salt-free construction, `serialization.md` §7.2; `SEED_COMMIT_DOMAIN = "CRP-seed-commit-v1"`); `revealed_seed` unset. | Stores `revealed_seed` only (the 32-byte seed; NO salt field — a 32-byte high-entropy seed is its own hiding randomness). Anyone can now recompute the assignment from the frozen method + seed and check it equals `cohort_root`. |
| 5 | `post_evidence_epoch` | `Active` → `Active` (self-loop) | C | `status == Active`; `now ≤ active_end` (or epoch `time_range` within the active window); `epoch_index` = previous + 1; roots well-formed; batch signature valid. | Creates an `EvidenceEpoch`; anchors signer-set + observations roots and integer counts. Repeatable. |
| 6 | `submit_evaluation` | `Active` → `Evaluating` (first submission) or `Evaluating` → `Evaluating` (corrected re-submission after an upheld challenge) | E | `status == Active` **or** (`status == Evaluating` **and** `evaluation_valid == false` **and** `open_challenges == 0`); `now ≥ active_end`; `revealed_seed` set; at least one `EvidenceEpoch`; echoed `analysis_container_digest` equals the frozen one; `now ≤ evaluation_deadline`. | (Re)creates/replaces the `Evaluation` with `result_artifact_hash` + `reward_root`; sets `evaluation_valid = true`; **sets `challenge_window_end = now + challenge_window_seconds`** and **initializes `open_challenges = 0`** (a fresh, absolute window is written here — never derived elsewhere — so no earlier event can shorten it); `status = Evaluating`. Re-submission is legal only to replace an evaluation that a prior challenge upheld as invalid. |
| 7 | `open_challenge` | `Evaluating` → `Challenged` (first) or `Challenged` → `Challenged` (additional, self-loop) | X | `status ∈ {Evaluating, Challenged}`; `evaluation_valid == true`; `now < challenge_window_end` (strictly within the open window); bond ≥ `challenge_bond_base_units` escrowed. | Creates a `Challenge` (its own account, `resolution` unset); escrows the bond; `open_challenges += 1`; `status = Challenged`. Multiple challenges may attach concurrently; each is independent. |
| 8 | `resolve_challenge` | `Challenged` → `Challenged` (`open_challenges` still `> 0` after decrement) or `Challenged` → `Evaluating` (`open_challenges` reaches `0`) | M | `status == Challenged`; the target `Challenge.resolution` is unset; multisig threshold; `resolution` references a verifier-CLI outcome (`upheld` or `dismissed`). | Sets `Challenge.resolution` and **releases that challenge's bond immediately and independently of any other challenge's order**: returned to the challenger if `upheld`, forfeited to `experiment.coordinator` if `dismissed`. Decrements `open_challenges` by 1. If `resolution == upheld`, sets `evaluation_valid = false` (the `Evaluation`'s `reward_root` becomes ineligible for finalize; a corrected `submit_evaluation` is required — tx6). **State leaves `Challenged` only when `open_challenges` reaches 0**, transitioning to `Evaluating`; while `open_challenges > 0` the status stays `Challenged` and every still-open `Challenge` remains independently resolvable with its bond releasable regardless of resolution order. |
| 9 | `finalize_distribution` | `Evaluating` → `Final` | M | `status == Evaluating`; **`now ≥ challenge_window_end`**; **`open_challenges == 0`**; `evaluation_valid == true` (a non-invalidated `Evaluation` is present); multisig threshold. *(No `ever_challenged` short-circuit exists; a dismissed challenge cannot shorten the window for a not-yet-opened honest challenge, and the two conjuncts cannot deadlock because the window always elapses and `resolve_challenge` always drives `open_challenges` to 0.)* | Creates `Distribution`; locks `reward_root`; records `total_allocated_base_units` (advisory, ≤ budget — see `reward-policy.md` §"Advisory on-chain accounting") + `unallocated_base_units` (recoverable); `status = Final`; opens claim window (`claim_window_seconds`). |
| 10 | `claim_reward` | `Final` → `Final` (self-loop) | P | `status == Final`; within claim window; Merkle proof of the reward leaf against the finalized `reward_root`; no existing `ClaimReceipt` for that leaf (nullifier unused). | Creates `ClaimReceipt` (single-use nullifier); transfers the leaf amount to the participant. Repeatable across distinct leaves. |
| 11 | `close_experiment` | `Final` → `Closed` | M or ∅ | `status == Final`; claim window elapsed. | Recovers unallocated + unclaimed budget to the funding authority; `status = Closed`. Terminal. |
| 12 | `abort_experiment` | `Frozen` / `Active` / `Evaluating` / `Challenged` → `Closed` (`aborted = true`) | M **or** ∅ | `status ∈ {Frozen, Active, Evaluating, Challenged}` (any pre-`Final` state); **no `Distribution` and no `ClaimReceipt` exists** (asserted defensively — see note below); **and** one of: (a) **multisig** threshold met; or (b) **permissionless timeout** — `now > evaluation_deadline + ProtocolConfig.abort_grace_seconds` with `status` never having reached `Final`. | Returns the full experiment vault (`budget_base_units`, un-touched pre-`Final`) to `experiment.coordinator`; **refunds every still-open `Challenge` bond to its respective challenger** (un-adjudicated bonds are returned, never forfeited); already-resolved challenges keep their prior resolution; sets `aborted = true`; `status = Closed`. Terminal. |

Notes:
- Self-loops (`reveal_seed`, `post_evidence_epoch`, `claim_reward`, and the additional-challenge
  and multi-resolution forms of `open_challenge` / `resolve_challenge`) do not always change
  `status`; they are listed as transitions because they are gated by it.
- The only way from `Frozen` forward is `publish_cohort_root`; the only path to reveal the seed
  is through `Active`, which is only reachable after `Frozen`. This is the structural encoding of
  freeze-before-reveal (Invariant 1).
- If no challenge is opened, the flow is `Evaluating → Final` directly (transition 9); the
  `Challenged` state is entered only when a challenge exists. Finalization is **always** taken from
  `Evaluating`: the settlement flow never finalizes directly out of `Challenged`, because tx8 only
  leaves `Challenged` (returning to `Evaluating`) once `open_challenges` has reached 0.
- **Challenge-window guard (tx9, security finding M1).** The finalize guard is the conjunction
  `now ≥ challenge_window_end AND open_challenges == 0`. There is no `ever_challenged` flag and no
  short-circuit on "a challenge was ever opened": a single challenge that is opened and then
  **dismissed** decrements `open_challenges` back toward 0 but can never collapse the window for a
  not-yet-opened honest challenger, because the `now ≥ challenge_window_end` conjunct still stands.
  The guard cannot deadlock: `challenge_window_end` is a fixed absolute timestamp that always
  elapses, and `resolve_challenge` monotonically drives `open_challenges` to 0.
- **Multi-challenge resolution (tx8, security finding H2).** `open_challenges` is the sole gate for
  leaving `Challenged`. Each `resolve_challenge` resolves exactly one `Challenge`, releases exactly
  that bond, and decrements the counter; challenges are resolvable in any order and one upheld
  resolution invalidates the evaluation (`evaluation_valid = false`) regardless of when it lands in
  the sequence. The state returns to `Evaluating` only on the resolution that brings
  `open_challenges` to 0.
- **Abort and claims (tx12, security finding H1).** `abort_experiment` is reachable only from
  pre-`Final` states, and a `ClaimReceipt` can be created only from `Final` (tx10); therefore no
  claim can ever have occurred when `abort_experiment` runs. The "no `Distribution` and no
  `ClaimReceipt` exists" precondition is a defensive assertion of that structural fact — it makes
  the "cannot abort after any claim" property explicit and locally checkable rather than relying on
  the reachability argument alone. Abort returns the vault to the coordinator and refunds all
  still-open challenge bonds; it is the bounded escape from the pre-`Final` fund trap, available
  either by multisig at any time or permissionlessly after `evaluation_deadline +
  abort_grace_seconds`.

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
| `Frozen` | `freeze_experiment` | `publish_cohort_root`, `abort_experiment` |
| `Active` | `publish_cohort_root` | `reveal_seed`, `post_evidence_epoch` (self), `submit_evaluation`, `abort_experiment` |
| `Evaluating` | `submit_evaluation`, last `resolve_challenge` (open_challenges → 0) | `submit_evaluation` (self, corrected re-submission), `open_challenge`, `finalize_distribution`, `abort_experiment` |
| `Challenged` | `open_challenge` | `resolve_challenge`, `open_challenge` (self, additional), `abort_experiment` |
| `Final` | `finalize_distribution` | `claim_reward` (self), `close_experiment` |
| `Closed` | `close_experiment` (normal), `abort_experiment` (`aborted = true`) | terminal |

No state other than `Closed` lacks an outgoing transition; every state is reachable from
`Draft`. `Closed` is the sole terminal state, entered either normally (`close_experiment`, after a
completed `Final`) or via `abort_experiment` (with the `aborted = true` marker) from any pre-`Final`
state — so there is no pre-`Final` state from which funds can become permanently trapped. All
**12 instructions** (tx1–tx12) and all **8 accounts** appear above.

## 5. Revision history

Versioning is two-track: a **wire/hash contract version** (governs the manifest/evidence schemas,
`serialization.md`, all golden hashes) and this document's **state-machine / protocol-behavior
version**. They advance independently; a behavior-only change does not bump the wire contract.
The wire/hash contract's own revision history lives in `serialization.md` §9; it is currently at
**1.1.0** (advanced additively by `serialization.md` v1.1, residuals A/B/C — no golden hash changed).
The state-machine v1.1.0 entry below was a behavior-only change and did not itself move the wire
contract (which was 1.0.0 at that time).

### v1.1.0 — settlement-flow hardening (this revision)

- **Wire/hash contract: 1.0.0, UNCHANGED.** No manifest field, no schema, no golden hash, and no
  `serialization.md` byte changed. The manifest `spec_version` stays `"1.0.0"` and a v1.0.0 manifest
  hashes identically under v1.1. This is a behavior-only, additive revision.
- **tx6 `submit_evaluation` tightened.** Now also legal as a self-transition `Evaluating →
  Evaluating` to replace an evaluation that a challenge upheld as invalid. It writes an **absolute**
  `challenge_window_end = now + challenge_window_seconds` and re-initializes `open_challenges = 0`
  and `evaluation_valid = true` at submission time, so the finalize window is defined in exactly one
  place and cannot be shortened by any earlier event.
- **tx8 `resolve_challenge` made crisp (security finding H2).** `open_challenges` is the single gate
  for leaving `Challenged`. Each resolution resolves one challenge, releases exactly that bond
  (returned if upheld, forfeited to the coordinator if dismissed) independently of order, and
  decrements the counter; any upheld resolution sets `evaluation_valid = false`. The state returns
  to `Evaluating` only when `open_challenges` reaches 0. Multi-challenge resolution is now
  order-independent and unambiguous.
- **tx9 `finalize_distribution` guard fixed (security finding M1).** Replaced the racy
  `now ≥ challenge_window_end OR ever_challenged` rule (an opened-then-dismissed challenge collapsed
  the window for honest not-yet-opened challengers) with the conjunction
  `now ≥ challenge_window_end AND open_challenges == 0`. The `ever_challenged` flag is removed from
  the protocol; it is no longer a gate. Finalize is now taken only from `Evaluating`. The guard can
  neither race ahead of the honest window nor deadlock.
- **tx12 `abort_experiment` added (security finding H1).** New 12th instruction. Provides a bounded
  escape from the pre-`Final` fund trap: from any pre-`Final` state (`Frozen`/`Active`/`Evaluating`/
  `Challenged`), gated by multisig **or** by a permissionless timeout (`now > evaluation_deadline +
  ProtocolConfig.abort_grace_seconds`), it returns the vault to the coordinator, refunds all
  still-open challenge bonds, sets `aborted = true`, and moves to `Closed`. It cannot run once any
  claim has occurred (structurally guaranteed — abort is unreachable from `Final` — and asserted
  defensively). No 8th status word: `Closed` is reused with the `aborted` marker.
- **Advisory accounting note (security finding M3).** Documented in `reward-policy.md` (§"Advisory
  on-chain accounting"): `Distribution.total_allocated_base_units` is an advisory upper bound
  (≤ budget), not cryptographically bound to the sum of reward leaves; the verifier CLI plus the
  challenge flow are the real guardrail (Invariant 6 — the chain verifies process, not truth).
- **Two deferred hardening items disclosed (no behavior change).** The M2 re-review's two Warnings
  touching this document — W2 (tx8 dismissed-challenge bond forfeits to the coordinator) and W1
  (tx12 permissionless timeout-abort can discard a valid in-window evaluation because tx1 does not
  enforce `abort_grace_seconds > challenge_window_seconds`) — are disclosed in `threat-model.md` §5,
  accepted for the devnet MVP (Invariant 7) and tracked for M4. No tx behavior changes here.

### v1.0.0 — initial frozen-READY state machine

11 core instructions, 8 accounts, `Draft → … → Closed`, freeze-before-reveal structurally encoded.
