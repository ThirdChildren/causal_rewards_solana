use anchor_lang::prelude::*;

// Every state transition emits a public event (CLAUDE.md).

#[event]
pub struct ProtocolInitialized {
    pub admin: Pubkey,
    pub schema_version: u16,
}

#[event]
pub struct ExperimentCreated {
    pub experiment: Pubkey,
    pub experiment_id: String,
    pub coordinator: Pubkey,
    pub evaluator: Pubkey,
    pub seed_commitment: [u8; 32],
    pub budget_base_units: u64,
}

#[event]
pub struct ExperimentFrozen {
    pub experiment: Pubkey,
    pub manifest_hash: [u8; 32],
}

#[event]
pub struct CohortRootPublished {
    pub experiment: Pubkey,
    pub cohort_root: [u8; 32],
    pub cohort_count: u32,
}

#[event]
pub struct SeedRevealed {
    pub experiment: Pubkey,
    pub seed_commitment: [u8; 32],
    pub revealed_seed: [u8; 32],
}

#[event]
pub struct StatusTransitioned {
    pub experiment: Pubkey,
    pub from: u8,
    pub to: u8,
    pub caller_program: Pubkey,
}

/// Emitted when `abort_experiment` (tx12) drives a pre-`Final` experiment to
/// `Closed` with `aborted = true` (security finding H1).
#[event]
pub struct ExperimentAborted {
    pub experiment: Pubkey,
    /// Status the experiment was in immediately before abort.
    pub from: u8,
    /// Open challenges recorded at abort time (their bonds are refundable via the
    /// challenge program's `refund_bond` crank).
    pub open_challenges: u32,
}
