//! evidence-registry — owns `EvidenceEpoch`. One compact record per epoch.
//!
//! Data minimization (Invariant 5): stores ONLY commitments/roots, a coarse cohort
//! label, a time range, and integer aggregate counts — never telemetry or coordinates.
//! Duplicate epochs are impossible (the epoch PDA `init` fails on collision); epochs
//! are monotonic with no gaps (previous epoch must already exist).

use anchor_lang::prelude::*;
use experiment_registry::state::{Experiment, ExperimentStatus};

declare_id!("Ex82ncHsgc4ZFWDYQQzwR96GNNnKd3YmoULnjWgb1neP");

pub const MAX_COHORT_ID_LEN: usize = 64;

#[program]
pub mod evidence_registry {
    use super::*;

    pub fn post_evidence_epoch(
        ctx: Context<PostEvidenceEpoch>,
        epoch_index: u64,
        args: EvidenceEpochArgs,
    ) -> Result<()> {
        let exp = &ctx.accounts.experiment;
        require!(exp.status == ExperimentStatus::Active, EvidenceError::WrongStatus);
        require_keys_eq!(
            ctx.accounts.coordinator.key(),
            exp.coordinator,
            EvidenceError::Unauthorized
        );

        // Coarse label + time-range validity (half-open [start,end), within active window).
        let cohort_bytes = args.cohort_id.as_bytes();
        require!(
            !cohort_bytes.is_empty() && cohort_bytes.len() <= MAX_COHORT_ID_LEN,
            EvidenceError::InvalidCohortId
        );
        require!(args.time_start < args.time_end, EvidenceError::InvalidTimeRange);
        require!(
            args.time_start >= exp.active_start && args.time_end <= exp.active_end,
            EvidenceError::TimeRangeOutsideActiveWindow
        );
        require!(
            (args.distinct_signers as u128) <= (args.accepted_count as u128 + args.rejected_count as u128),
            EvidenceError::InconsistentCounts
        );

        // Monotonic, no-gap epoch index. Duplicate is rejected by `init` on the PDA.
        if epoch_index > 0 {
            let prev = &ctx.accounts.prev_epoch;
            require!(prev.owner == &crate::ID, EvidenceError::PrevEpochMissing);
            let (expected_prev, _) = Pubkey::find_program_address(
                &[
                    b"epoch",
                    exp.key().as_ref(),
                    &epoch_index
                        .checked_sub(1)
                        .ok_or(EvidenceError::MathOverflow)?
                        .to_le_bytes(),
                ],
                &crate::ID,
            );
            require_keys_eq!(prev.key(), expected_prev, EvidenceError::PrevEpochMissing);
            require!(!prev.data_is_empty(), EvidenceError::PrevEpochMissing);
        }

        let ep = &mut ctx.accounts.evidence_epoch;
        ep.experiment = exp.key();
        ep.epoch_index = epoch_index;
        ep.cohort_id = args.cohort_id.clone();
        ep.time_start = args.time_start;
        ep.time_end = args.time_end;
        ep.signer_set_root = args.signer_set_root;
        ep.observations_root = args.observations_root;
        ep.accepted_count = args.accepted_count;
        ep.rejected_count = args.rejected_count;
        ep.distinct_signers = args.distinct_signers;
        ep.content_hash = args.content_hash;
        ep.producer = args.producer;
        ep.bump = ctx.bumps.evidence_epoch;

        emit!(EvidenceEpochPosted {
            experiment: exp.key(),
            epoch_index,
            cohort_id: args.cohort_id,
            time_start: args.time_start,
            time_end: args.time_end,
            signer_set_root: args.signer_set_root,
            observations_root: args.observations_root,
            accepted_count: args.accepted_count,
        });
        Ok(())
    }
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct EvidenceEpochArgs {
    pub cohort_id: String,
    pub time_start: i64,
    pub time_end: i64,
    pub signer_set_root: [u8; 32],
    pub observations_root: [u8; 32],
    pub accepted_count: u64,
    pub rejected_count: u64,
    pub distinct_signers: u64,
    pub content_hash: [u8; 32],
    pub producer: Pubkey,
}

#[account]
pub struct EvidenceEpoch {
    pub experiment: Pubkey,
    pub epoch_index: u64,
    pub cohort_id: String,
    pub time_start: i64,
    pub time_end: i64,
    pub signer_set_root: [u8; 32],
    pub observations_root: [u8; 32],
    pub accepted_count: u64,
    pub rejected_count: u64,
    pub distinct_signers: u64,
    pub content_hash: [u8; 32],
    pub producer: Pubkey,
    pub bump: u8,
}

impl EvidenceEpoch {
    pub const SPACE: usize = 8
        + 32
        + 8
        + 4 + MAX_COHORT_ID_LEN
        + 8 + 8
        + 32 + 32
        + 8 + 8 + 8
        + 32
        + 32
        + 1;
}

#[derive(Accounts)]
#[instruction(epoch_index: u64)]
pub struct PostEvidenceEpoch<'info> {
    pub experiment: Account<'info, Experiment>,
    #[account(
        init,
        payer = coordinator,
        space = EvidenceEpoch::SPACE,
        seeds = [b"epoch", experiment.key().as_ref(), &epoch_index.to_le_bytes()],
        bump
    )]
    pub evidence_epoch: Account<'info, EvidenceEpoch>,
    /// CHECK: previous epoch PDA; validated in-handler (must exist when epoch_index>0).
    pub prev_epoch: UncheckedAccount<'info>,
    #[account(mut)]
    pub coordinator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[event]
pub struct EvidenceEpochPosted {
    pub experiment: Pubkey,
    pub epoch_index: u64,
    pub cohort_id: String,
    pub time_start: i64,
    pub time_end: i64,
    pub signer_set_root: [u8; 32],
    pub observations_root: [u8; 32],
    pub accepted_count: u64,
}

#[error_code]
pub enum EvidenceError {
    #[msg("Experiment is not Active")]
    WrongStatus,
    #[msg("Signer is not the coordinator")]
    Unauthorized,
    #[msg("cohort_id empty or too long")]
    InvalidCohortId,
    #[msg("time_range invalid: require start < end")]
    InvalidTimeRange,
    #[msg("time_range outside the active window")]
    TimeRangeOutsideActiveWindow,
    #[msg("distinct_signers exceeds total observation count")]
    InconsistentCounts,
    #[msg("previous epoch does not exist (epochs must be monotonic, no gaps)")]
    PrevEpochMissing,
    #[msg("Checked arithmetic overflow")]
    MathOverflow,
}
