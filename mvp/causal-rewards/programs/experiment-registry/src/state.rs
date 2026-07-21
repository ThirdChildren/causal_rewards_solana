use anchor_lang::prelude::*;

pub const MAX_SIGNERS: usize = 10;
pub const MAX_EXPERIMENT_ID_LEN: usize = 64;

/// Devnet-only guard value (Invariant 7).
pub const CLUSTER_DEVNET: u8 = 0;

#[derive(AnchorSerialize, AnchorDeserialize, Clone, Copy, PartialEq, Eq, Debug)]
pub enum ExperimentStatus {
    Draft,
    Frozen,
    Active,
    Evaluating,
    Challenged,
    Final,
    Closed,
}

/// Global config. Created once at program init.
#[account]
pub struct ProtocolConfig {
    pub admin: Pubkey,
    /// Hard-zero fee (Invariant 7). Asserted == 0 at init.
    pub fee_bps: u16,
    /// Emergency pause: blocks state-advancing instructions. Cannot rewrite frozen records.
    pub paused: bool,
    /// Devnet guard (Invariant 7). Must equal CLUSTER_DEVNET.
    pub cluster: u8,
    pub schema_version: u16,
    /// Registered satellite program ids authorized to advance Experiment.status via CPI.
    pub evidence_program: Pubkey,
    pub settlement_program: Pubkey,
    pub challenge_program: Pubkey,
    /// Timeout offset (seconds) for the permissionless `abort_experiment` path
    /// (state-machine v1.1 tx12): abort is permissionlessly reachable once
    /// `now > evaluation_deadline + abort_grace_seconds`.
    pub abort_grace_seconds: i64,
    pub bump: u8,
}

impl ProtocolConfig {
    pub const SPACE: usize = 8 + 32 + 2 + 1 + 1 + 2 + 32 + 32 + 32 + 8 + 1;
}

/// Per-experiment record. Holds only hashes / roots / status / windows (Invariant 5).
#[account]
pub struct Experiment {
    pub status: ExperimentStatus,
    pub coordinator: Pubkey,
    pub evaluator: Pubkey,
    /// m-of-n multisig.
    pub authority_threshold: u8,
    pub authority_signers: Vec<Pubkey>,

    pub experiment_id: String,

    // ---- Frozen at `Frozen` (immutability set, state-machine §3) ----
    pub manifest_hash: [u8; 32],
    pub analysis_container_digest: [u8; 32],
    pub reward_curve_hash: [u8; 32],
    pub seed_commitment: [u8; 32],
    pub mint: Pubkey,
    pub vault: Pubkey,
    pub budget_base_units: u64,
    pub challenge_bond_base_units: u64,
    pub freeze_by: i64,
    pub active_start: i64,
    pub active_end: i64,
    pub evaluation_deadline: i64,
    pub challenge_window_seconds: i64,
    pub claim_window_seconds: i64,

    // ---- Append-only after freeze ----
    pub cohort_published: bool,
    /// Revealed once, after publish_cohort_root (freeze-before-reveal, Invariant 1).
    pub revealed_seed: Option<[u8; 32]>,

    // ---- Phase bookkeeping (written only by registry, incl. CPI transitions) ----
    /// True iff a live, non-invalidated `Evaluation` is present (set at
    /// `submit_evaluation` / tx6, cleared to `false` by an upheld challenge / tx8).
    /// It is the sole `evaluation is finalizable` predicate (state-machine v1.1);
    /// starts `false` at create (no evaluation yet). Replaces the previous
    /// `evaluation_present`/`evaluation_invalidated` pair and the removed
    /// `ever_challenged` gate (security findings H2/M1).
    pub evaluation_valid: bool,
    /// `open_challenges` is the SOLE gate for leaving `Challenged` (tx8). u32 count of
    /// unresolved `Challenge` accounts; checked_add/sub only.
    pub open_challenges: u32,
    /// Absolute unix ts written ONCE at `submit_evaluation` (tx6); the finalize window
    /// is defined only here so no earlier event can shorten it (security finding M1).
    pub challenge_window_end: i64,
    pub claim_window_end: i64,
    /// Set only by `abort_experiment` (tx12). Marks a `Closed` experiment as aborted
    /// (pre-`Final` escape from the fund trap, security finding H1). No 8th status word.
    pub aborted: bool,

    pub created_at: i64,
    pub bump: u8,
    pub vault_bump: u8,
}

impl Experiment {
    pub const SPACE: usize = 8
        + 1                                   // status
        + 32                                  // coordinator
        + 32                                  // evaluator
        + 1                                   // threshold
        + 4 + MAX_SIGNERS * 32                // signers vec
        + 4 + MAX_EXPERIMENT_ID_LEN           // experiment_id
        + 32 + 32 + 32 + 32                   // manifest/container/curve/seed_commit
        + 32 + 32                             // mint, vault
        + 8 + 8                               // budget, bond
        + 8 * 6                               // windows
        + 1                                   // cohort_published
        + 1 + 32                              // revealed_seed Option
        + 1                                   // evaluation_valid
        + 4                                   // open_challenges
        + 8 + 8                               // challenge_window_end, claim_window_end
        + 1                                   // aborted
        + 8                                   // created_at
        + 1 + 1; // bump, vault_bump
}

/// Assignment/cohort commitment. Published BEFORE the seed is revealed.
#[account]
pub struct CohortSet {
    pub experiment: Pubkey,
    pub cohort_root: [u8; 32],
    pub cohort_count: u32,
    pub bump: u8,
}

impl CohortSet {
    pub const SPACE: usize = 8 + 32 + 32 + 4 + 1;
}
