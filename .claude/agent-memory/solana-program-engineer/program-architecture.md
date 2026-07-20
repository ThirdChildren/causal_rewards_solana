---
name: program-architecture
description: Four-program split, who owns/writes Experiment.status, cross-program CPI auth, PDA seed conventions, error-code map
metadata:
  type: reference
---

# On-chain program architecture (M2)

Anchor workspace at `mvp/causal-rewards/`. Four programs + one shared crate `crp-crypto` (sha256/merkle/seed/assignment; host-tested vs test-vectors).

## Program split & instructions
- **experiment-registry** — owns `ProtocolConfig`, `Experiment`, `CohortSet`. Instructions: `init_protocol_config`, `create_experiment`, `freeze_experiment`, `publish_cohort_root`, `reveal_seed`. Also owns the **status field** and exposes CPI-only transitions: `mark_evaluating`, `mark_challenged`, `mark_evaluating_from_resolve`, `mark_final`, `mark_closed`.
- **evidence-registry** — owns `EvidenceEpoch`. `post_evidence_epoch`. Reads Experiment (no write).
- **settlement** — owns `Evaluation`, `Distribution`, `ClaimReceipt`. `submit_evaluation`, `finalize_distribution`, `claim_reward`, `close_experiment`. CPIs experiment-registry for status.
- **challenge** — owns `Challenge`. `open_challenge`, `resolve_challenge`. CPIs experiment-registry for status.

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
