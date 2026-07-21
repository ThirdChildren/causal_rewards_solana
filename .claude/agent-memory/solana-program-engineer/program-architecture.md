---
name: program-architecture
description: Four-program split, who owns/writes Experiment.status, cross-program CPI auth, PDA seed conventions, error-code map
metadata:
  type: reference
---

# On-chain program architecture (M2)

Anchor workspace at `mvp/causal-rewards/`. Four programs + one shared crate `crp-crypto` (sha256/merkle/seed/assignment; host-tested vs test-vectors).

## Program split & instructions
- **experiment-registry** — owns `ProtocolConfig`, `Experiment`, `CohortSet`. Instructions: `init_protocol_config`, `create_experiment`, `freeze_experiment`, `publish_cohort_root`, `reveal_seed`. Also owns the **status field** and exposes CPI-only transitions: `mark_evaluating`, `mark_challenged`, `resolve_upheld`, `resolve_dismissed`, `mark_final`, `mark_aborted`, `mark_closed`.
- **evidence-registry** — owns `EvidenceEpoch`. `post_evidence_epoch`. Reads Experiment (no write).
- **settlement** — owns `Evaluation`, `Distribution`, `ClaimReceipt`. `submit_evaluation`, `finalize_distribution`, `claim_reward`, `close_experiment`, `abort_experiment`. CPIs experiment-registry for status.
- **challenge** — owns `Challenge`. `open_challenge`, `resolve_challenge`, `refund_bond`. CPIs experiment-registry for status.

## State-machine v1.1 (settlement-flow hardening; security findings H1/H2/M1)
Spec `specs/state-machine.md` is behavior-version 1.1.0 (wire/hash contract still 1.0.0, no hashed artifact changed). Implemented:
- **H2 multi-challenge (tx8).** `Experiment.open_challenges` (u32) is the SOLE gate for leaving `Challenged`. `resolve_upheld`/`resolve_dismissed` each decrement by 1 (checked_sub); upheld sets `evaluation_valid=false`; status returns to `Evaluating` ONLY when the counter hits 0 (order-independent). The challenge program's `resolve_challenge` releases exactly that one bond immediately (upheld→challenger, dismissed→`experiment.coordinator`).
- **M1 finalize guard (tx9).** `mark_final` is taken ONLY from `Evaluating` and requires `now>=challenge_window_end AND open_challenges==0 AND evaluation_valid`. `ever_challenged` field/gate was REMOVED entirely. `challenge_window_end` is an ABSOLUTE unix ts written once by `mark_evaluating` at `submit_evaluation` (tx6); tx6 also allows the `Evaluating→Evaluating` corrected-resubmission self-loop when `!evaluation_valid && open_challenges==0`.
- **H1 abort (tx12).** `settlement::abort_experiment` returns the FULL vault to `experiment.coordinator` and CPIs registry `mark_aborted` (Frozen/Active/Evaluating/Challenged → `Closed` with `aborted=true`; reuses Closed, no 8th status). Gate: multisig threshold OR permissionless timeout `now > evaluation_deadline + ProtocolConfig.abort_grace_seconds`. Defensive: asserts the Distribution PDA is uninitialized (structurally no claim can exist pre-Final). Bonds are under the CHALLENGE program's PDA authority, so they are refunded separately/permissionlessly via `challenge::refund_bond` (gated on `experiment.aborted`, resolution UNSET→REFUNDED replay guard). `mark_aborted` is NOT gated on `paused` (so pausing cannot trap funds).

## Field model change (v1.1)
`Experiment` phase bookkeeping: the old `evaluation_present`+`evaluation_invalidated`+`ever_challenged` trio was replaced by a single `evaluation_valid: bool` (starts false at create; true at submit; false after an upheld challenge). New: `aborted: bool`. `ProtocolConfig` gained `abort_grace_seconds: i64` (add to `init_protocol_config` args). `challenge::Challenge.resolution` now has code 3 = REFUNDED.

## Cross-program status ownership
`Experiment.status` is written **only** by experiment-registry. Satellite programs advance it via **CPI into experiment-registry**, authenticated by a program-authority PDA: satellite signs the CPI with `seeds=[b"cpi_authority", bump]` under its own program id; experiment-registry verifies the signer PDA via Anchor `seeds::program = protocol_config.<caller>_program`. ProtocolConfig stores the three satellite program ids. Role signers (evaluator E, multisig M, challenger X, participant P) are enforced in the originating satellite instruction and passed through.

## PDA seed conventions
- ProtocolConfig: `[b"protocol_config"]`
- Experiment: `[b"experiment", experiment_id_hash]` where `experiment_id_hash = sha256("CRP-exp-id"||experiment_id)` (id can exceed 32-byte seed limit).
- Vault (token acct): `[b"vault", experiment]`; vault authority = the Experiment PDA itself.
- CohortSet: `[b"cohort_set", experiment]`
- EvidenceEpoch: `[b"epoch", experiment, epoch_index_le_u64]` (init fails on duplicate => no duplicate epochs; monotonic enforced by requiring prev epoch to exist).
- Evaluation: `[b"evaluation", experiment]` (single current evaluation; replaced after upheld challenge)
- Distribution: `[b"distribution", experiment]`
- ClaimReceipt (nullifier): `[b"claim", experiment, leaf_index_le_u64]` — init_if_needed-free; `init` fails if exists => single-use.
- Challenge: `[b"challenge", experiment, challenger]`
- CPI authority (each satellite): `[b"cpi_authority"]`

## Status enum
`Draft=0, Frozen=1, Active=2, Evaluating=3, Challenged=4, Final=5, Closed=6`.

## Error-code map (custom errors, per program; see each `error.rs`)
Common themes: `WrongStatus`, `Unauthorized`, `SeedCommitmentMismatch`, `SeedAlreadyRevealed`, `ContainerDigestMismatch`, `EpochNotMonotonic`, `WindowClosed`/`WindowNotOpen`, `MultisigThresholdNotMet`, `InvalidMerkleProof`, `AlreadyClaimed`, `BondTooLow`, `ChallengeStillOpen`, `NotDevnet`, `FeeNotZero`, `MathOverflow`.

Fees hard-zero (`fee_bps==0` asserted in init). Emergency `paused` flag on ProtocolConfig blocks state-advancing ix. Devnet-only guard: `ProtocolConfig.cluster==0(devnet)`.
