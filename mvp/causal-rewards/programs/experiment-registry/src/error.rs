use anchor_lang::prelude::*;

#[error_code]
pub enum RegistryError {
    #[msg("Protocol config cluster is not devnet (Invariant 7)")]
    NotDevnet,
    #[msg("Fee must be hard-zero (Invariant 7)")]
    FeeNotZero,
    #[msg("Protocol is paused (emergency)")]
    Paused,
    #[msg("Experiment is not in the required status for this transition")]
    WrongStatus,
    #[msg("Signer is not authorized for this action")]
    Unauthorized,
    #[msg("Multisig threshold not met")]
    MultisigThresholdNotMet,
    #[msg("Invalid multisig configuration")]
    InvalidMultisig,
    #[msg("experiment_id is empty or too long")]
    InvalidExperimentId,
    #[msg("Window ordering invalid: require active_start <= active_end <= evaluation_deadline")]
    InvalidWindowOrdering,
    #[msg("freeze_by is in the past")]
    FreezeDeadlinePassed,
    #[msg("Freeze deadline has passed; cannot freeze")]
    FreezeWindowClosed,
    #[msg("Revealed seed does not open the frozen seed commitment (Invariant 1)")]
    SeedCommitmentMismatch,
    #[msg("Seed already revealed; assignment cannot be re-chosen")]
    SeedAlreadyRevealed,
    #[msg("Cohort root already published")]
    CohortAlreadyPublished,
    #[msg("Seed must be revealed only after the cohort root is published")]
    CohortNotPublished,
    #[msg("Caller program is not the registered authority for this transition")]
    UnauthorizedCaller,
    #[msg("Evaluation was invalidated by an upheld challenge; resubmit required")]
    EvaluationInvalidated,
    #[msg("Challenge window has not elapsed and challenges remain unresolved")]
    ChallengeWindowNotElapsed,
    #[msg("Open challenges remain unresolved")]
    OpenChallengesRemain,
    #[msg("Claim window has not elapsed")]
    ClaimWindowNotElapsed,
    #[msg("Checked arithmetic overflow")]
    MathOverflow,
    #[msg("Threshold must be >= 1 and <= number of signers")]
    InvalidThreshold,
    #[msg("Vault mint does not match experiment mint")]
    MintMismatch,
}
