---
name: m2-findings
description: Living findings log for the M2 Solana programs review (experiment-registry, evidence-registry, settlement, challenge, crp-crypto)
metadata:
  type: project
---

# M2 Programs Security Findings Log

First full review: 2026-07-20 (spec-v1-frozen). Reviewer = security-reviewer. Read-only.
Programs at `mvp/causal-rewards/programs/*` + `crates/crp-crypto`.

**Why:** M2 acceptance (devnet deploy + integration tests + assignment vectors). Milestone
cannot be "done" while a Critical/High is open. SDK is meant to be built against these next.
**How to apply:** consult before any re-review; do not re-litigate resolved items; verify
each open item against current code (grep the instruction) before re-reporting.

## RESOLVED findings (re-review 2026-07-21, state-machine v1.1)

- **H1 — CLOSED (2026-07-21).** `settlement::abort_experiment` (lib.rs L292-358) +
  `registry::mark_aborted` (L387-410) + `challenge::refund_bond` (L187-230) added. Pre-Final
  escape: multisig OR permissionless timeout (`now > evaluation_deadline + abort_grace_seconds`);
  vault returns only to `experiment.coordinator` (recovery_token owner constraint); open bonds
  refunded exactly once (UNSET->REFUNDED guard, replay-rejected); unreachable after finalize
  (distribution.data_is_empty assertion + mark_aborted status set excludes Final); not paused-gated
  so pause can't trap funds. Verified + tested. NOTE new Warning W1 (permissionless-abort race), below.
- **H2 — CLOSED (2026-07-21).** `resolve_upheld`/`resolve_dismissed` (registry L327-358) each
  resolve one challenge, decrement open_challenges via checked_sub, and leave `Challenged` ONLY at
  0. checked_sub cannot underflow (Challenged implies open_challenges>=1). Bond released exactly
  once per challenge (challenge::resolve_challenge UNSET-guard, own bond_vault, order-independent).
  Tested: two concurrent order-independent + uphold-with-pending.
- **M1 — CLOSED (2026-07-21).** `mark_final` (registry L365-378) = Evaluating AND evaluation_valid
  AND open_challenges==0 AND now>=challenge_window_end AND multisig. `ever_challenged` fully removed
  from logic (only doc/IDL text remains). `challenge_window_end` written only in mark_evaluating
  (per-evaluation, forward-only from submit time) — cannot be moved to shortcut the window. Tested.

## NEW findings (re-review 2026-07-21)

- **W1 (Warning, should-fix, NOT a GO-blocker) — permissionless-timeout abort can preempt a
  finalizable evaluation (settlement::abort_experiment L304-316).** `finalize_distribution` has no
  upper time bound and needs multisig; the permissionless abort opens at `evaluation_deadline +
  abort_grace_seconds` (global config, NOT validated against per-experiment
  `challenge_window_seconds` at create). If grace is small relative to challenge_window, or simply
  once past the timeout while a slow multisig hasn't finalized yet, ANY caller can abort a valid,
  ready-to-finalize evaluation from `Evaluating` — nuking the settlement (funds back to coordinator,
  earned rewards never paid). No theft (coordinator recovers budget), so devnet-acceptable, but it
  is a liveness/griefing weakness that inverts the "finality can't be blocked" property. Fix:
  (a) enforce `abort_grace_seconds > challenge_window_seconds` at create_experiment, and/or
  (b) block the permissionless (timed_out) branch when `status==Evaluating && evaluation_valid`
  (leave multisig-abort available) — combine with a generous grace so a live multisig always wins
  the race. Stall cases (evaluation_valid==false) stay permissionlessly abortable.
- **W2 (Warning / economic, should-fix before any real value) — dismissed-bond forfeit to
  coordinator is a collusion incentive (challenge::resolve_challenge L113-119).** Resolution is
  multisig-gated and the coordinator is typically aligned with the multisig; a coordinator-controlled
  multisig can DISMISS a valid challenge (that correctly flags a bad evaluation), pocket the honest
  challenger's bond, and finalize an inflated distribution. threat-model §3.4 only offers an
  off-chain deterrent (verifier re-run / reproducibility), no on-chain control; the collusion row is
  not even listed. Devnet-acceptable (zero-value bonds). Recommend routing dismissed forfeits to a
  NEUTRAL sink (burn or config treasury not controlled by coordinator) and adding the collusion row
  to §3.4. Preserves anti-griefing cost, removes the adjudicator's financial stake in the outcome.

## MEDIUM / LOW / INFO (open, non-blocking)
- **M2 — Reward-leaf determinism boundary (crp-crypto L189-206 + settlement claim).** On-chain
  claim hard-depends on the PROVISIONAL 48-byte BE preimage `recipient||amount_be||index_be`.
  serialization.md §6.2 defers reward leaf identity/ordering to M3. If M3 ratifies a different
  preimage, settlement claim verification must change → SDK claim path may need rework. Flagged,
  not blocking (ratification in flight).
- **M3 — total_allocated not bound to reward_root (settlement finalize).**
  `total_allocated_base_units` is caller-supplied and only checked ≤ budget; not cryptographically
  tied to the committed leaves. Over/under accounting possible, but vault balance = budget caps
  real payout and unclaimed returns to coordinator, so no funds are created. Relies on
  verifier+challenge (consistent with Inv 6). Note only.
- **L1 — post_evidence_epoch does not verify batch signature on-chain** (spec transition 5 says
  "batch signature valid"); only stores `producer` pubkey. Signature checked off-chain by verifier.
- **L2 — Single-key emergency pause** (ProtocolConfig.admin). Admin can pause indefinitely (grief);
  no auto-expiry / not multisig. Acceptable as emergency-pause-only per CLAUDE.md; consider hardening.
- **INFO — manifest_hash / cluster guard are attestations, not on-chain-verifiable.** manifest bytes
  never on-chain; `cluster` is a stored flag, not a real network check. Inherent; multisig + verifier
  cover it.

## PASS (verified this round)

- Freeze-before-reveal structural encoding (Inv 1): reveal gated on Active+cohort_published+seed
  unset + commitment recompute; publish gated on Frozen+seed unset; frozen fields never rewritten.
- Single-use claims: ClaimReceipt PDA `init` on seed [claim, experiment, leaf_index]; no cross-exp
  collision (experiment in seed + per-exp reward_root + per-exp vault). recipient bound in leaf + signer.
- Merkle: 0x00 leaf / 0x01 node domain separation, promotion (not duplication), per-tree domain tags,
  empty=32 zero bytes. Second-preimage (node-as-leaf) blocked. Matches serialization.md §6.
- Checked math + hard-zero fees (fee_bps==0 asserted, never applied).
- CPI authority: satellite status writes gated by seeds::program CPI-authority PDA signer; status
  only writable by registry. Multisig m-of-n distinct-signer count enforced on freeze/finalize/resolve.
- Data minimization (Inv 5): only hashes/roots/counts/coarse labels/pubkeys on-chain.

## Threat-case coverage matrix (control verified? / test present?)

| Threat | Control found | Adversarial test |
| --- | --- | --- |
| Post-result rule change | freeze immutability set, no rewrite path | partial (re-freeze/re-publish rejected) |
| Assignment manipulation (seed choice) | publish-before-reveal + on-chain commitment recompute | reveal-mismatch rejected |
| Duplicate/replayed evidence | epoch PDA init + monotonic prev-epoch | duplicate epoch rejected |
| Reward-root substitution | dist.reward_root read from bound Evaluation PDA | no direct test |
| Claim replay / double-claim | ClaimReceipt init nullifier | double-claim + forged-amount rejected |
| Evaluator tampering | container digest echo + verifier/challenge | none on-chain (by design) |
| Authority compromise | multisig; single-key pause (L2) | freeze-below-threshold rejected |
| Griefing / indefinite challenge | bonds + window | ONLY single dismissed challenge; H2 multi-upheld UNTESTED |
| Fund stranding | close_experiment (Final only) — GAP H1 | none |
