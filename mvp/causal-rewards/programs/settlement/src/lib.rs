//! settlement — owns `Evaluation`, `Distribution`, `ClaimReceipt`.
//!
//! * `submit_evaluation` records the result-artifact hash + reward root; CPIs the
//!   registry to advance Active -> Evaluating and open the challenge window.
//! * `finalize_distribution` locks the reward root and the recoverable remainder;
//!   CPIs the registry to advance -> Final. Multisig-gated.
//! * `claim_reward` verifies a Merkle proof of the reward leaf against the finalized
//!   root and transfers the leaf amount. SINGLE-USE: the `ClaimReceipt` PDA is the
//!   nullifier; `init` fails on a second claim of the same leaf (double-claim rejected).
//! * `close_experiment` recovers unclaimed/unallocated budget after the claim window.
//!
//! Fees are hard-zero (Invariant 7): no fee is ever deducted from a transfer.

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Token, TokenAccount, Transfer};
use experiment_registry::program::ExperimentRegistry;
use experiment_registry::state::{Experiment, ExperimentStatus, ProtocolConfig};

declare_id!("4YGzmSUZYxYQMJ4E9YiM7h8dv4KChVEKHuN5T2W5qn86");

pub const CPI_AUTHORITY_SEED: &[u8] = b"cpi_authority";
pub const VAULT_AUTHORITY_SEED: &[u8] = b"vault_authority";

#[program]
pub mod settlement {
    use super::*;

    pub fn submit_evaluation(
        ctx: Context<SubmitEvaluation>,
        result_artifact_hash: [u8; 32],
        reward_root: [u8; 32],
        analysis_container_digest: [u8; 32],
    ) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let exp = &ctx.accounts.experiment;

        // Guards (state-machine v1.1 tx6): Active (first submission) OR the
        // Evaluating -> Evaluating self-loop to replace an evaluation that a prior
        // challenge upheld as invalid (`evaluation_valid == false`) once every
        // challenge is resolved (`open_challenges == 0`).
        let first_submit = exp.status == ExperimentStatus::Active;
        let resubmit = exp.status == ExperimentStatus::Evaluating
            && !exp.evaluation_valid
            && exp.open_challenges == 0;
        require!(first_submit || resubmit, SettlementError::WrongStatus);
        require_keys_eq!(ctx.accounts.evaluator.key(), exp.evaluator, SettlementError::Unauthorized);
        require!(exp.revealed_seed.is_some(), SettlementError::SeedNotRevealed);
        require!(now >= exp.active_end, SettlementError::ActiveWindowNotEnded);
        require!(now <= exp.evaluation_deadline, SettlementError::EvaluationDeadlinePassed);
        require!(
            analysis_container_digest == exp.analysis_container_digest,
            SettlementError::ContainerDigestMismatch
        );

        // At least one EvidenceEpoch exists (epoch 0 PDA under the evidence program).
        let (epoch_zero, _) = Pubkey::find_program_address(
            &[b"epoch", exp.key().as_ref(), &0u64.to_le_bytes()],
            &ctx.accounts.protocol_config.evidence_program,
        );
        require_keys_eq!(ctx.accounts.epoch_zero.key(), epoch_zero, SettlementError::NoEvidence);
        require!(
            ctx.accounts.epoch_zero.owner == &ctx.accounts.protocol_config.evidence_program
                && !ctx.accounts.epoch_zero.data_is_empty(),
            SettlementError::NoEvidence
        );

        let challenge_window_end = now
            .checked_add(exp.challenge_window_seconds)
            .ok_or(SettlementError::MathOverflow)?;

        let ev = &mut ctx.accounts.evaluation;
        ev.experiment = exp.key();
        ev.result_artifact_hash = result_artifact_hash;
        ev.reward_root = reward_root;
        ev.analysis_container_digest = analysis_container_digest;
        ev.evaluator = ctx.accounts.evaluator.key();
        ev.bump = ctx.bumps.evaluation;

        // CPI: registry advances status (Active|reEvaluating -> Evaluating).
        let bump = ctx.bumps.cpi_authority;
        let seeds: &[&[&[u8]]] = &[&[CPI_AUTHORITY_SEED, &[bump]]];
        experiment_registry::cpi::mark_evaluating(
            CpiContext::new_with_signer(
                ctx.accounts.experiment_registry_program.key(),
                experiment_registry::cpi::accounts::MarkBySettlement {
                    protocol_config: ctx.accounts.protocol_config.to_account_info(),
                    experiment: ctx.accounts.experiment.to_account_info(),
                    caller_authority: ctx.accounts.cpi_authority.to_account_info(),
                },
                seeds,
            ),
            challenge_window_end,
        )?;

        emit!(EvaluationSubmitted {
            experiment: exp.key(),
            result_artifact_hash,
            reward_root,
            challenge_window_end,
        });
        Ok(())
    }

    pub fn finalize_distribution(
        ctx: Context<FinalizeDistribution>,
        total_allocated_base_units: u64,
    ) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let exp = &ctx.accounts.experiment;

        // Multisig gate (m-of-n signers in remaining_accounts).
        experiment_registry::verify_multisig(
            ctx.remaining_accounts,
            &exp.authority_signers,
            exp.authority_threshold,
        )
        .map_err(|_| error!(SettlementError::MultisigThresholdNotMet))?;

        require!(
            total_allocated_base_units <= exp.budget_base_units,
            SettlementError::AllocationExceedsBudget
        );
        let unallocated = exp
            .budget_base_units
            .checked_sub(total_allocated_base_units)
            .ok_or(SettlementError::MathOverflow)?;
        let claim_window_end = now
            .checked_add(exp.claim_window_seconds)
            .ok_or(SettlementError::MathOverflow)?;

        let dist = &mut ctx.accounts.distribution;
        dist.experiment = exp.key();
        dist.reward_root = ctx.accounts.evaluation.reward_root;
        dist.total_allocated_base_units = total_allocated_base_units;
        dist.unallocated_base_units = unallocated;
        dist.claim_window_end = claim_window_end;
        dist.bump = ctx.bumps.distribution;

        // CPI: registry advances -> Final (checks window / open challenges / invalidation).
        let bump = ctx.bumps.cpi_authority;
        let seeds: &[&[&[u8]]] = &[&[CPI_AUTHORITY_SEED, &[bump]]];
        experiment_registry::cpi::mark_final(
            CpiContext::new_with_signer(
                ctx.accounts.experiment_registry_program.key(),
                experiment_registry::cpi::accounts::MarkBySettlement {
                    protocol_config: ctx.accounts.protocol_config.to_account_info(),
                    experiment: ctx.accounts.experiment.to_account_info(),
                    caller_authority: ctx.accounts.cpi_authority.to_account_info(),
                },
                seeds,
            ),
            claim_window_end,
        )?;

        emit!(DistributionFinalized {
            experiment: exp.key(),
            reward_root: dist.reward_root,
            total_allocated_base_units,
            unallocated_base_units: unallocated,
            claim_window_end,
        });
        Ok(())
    }

    pub fn claim_reward(
        ctx: Context<ClaimReward>,
        leaf_index: u64,
        amount_base_units: u64,
        proof: Vec<ClaimProofStep>,
    ) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let exp = &ctx.accounts.experiment;
        require!(exp.status == ExperimentStatus::Final, SettlementError::WrongStatus);
        require!(
            now <= ctx.accounts.distribution.claim_window_end,
            SettlementError::ClaimWindowClosed
        );

        // Verify the Merkle proof of the reward leaf against the finalized root.
        let recipient = ctx.accounts.recipient.key().to_bytes();
        let leaf_hash = crp_crypto::reward_leaf_hash(&recipient, amount_base_units, leaf_index);
        let steps: Vec<crp_crypto::ProofStep> = proof
            .iter()
            .map(|s| crp_crypto::ProofStep {
                sibling: s.sibling,
                sibling_is_left: s.sibling_is_left,
            })
            .collect();
        require!(
            crp_crypto::verify_proof(&leaf_hash, &steps, &ctx.accounts.distribution.reward_root),
            SettlementError::InvalidMerkleProof
        );

        // Record the single-use nullifier (the ClaimReceipt PDA `init` already guarantees
        // this leaf_index was never claimed; a second attempt fails at account creation).
        let rc = &mut ctx.accounts.claim_receipt;
        rc.experiment = exp.key();
        rc.leaf_index = leaf_index;
        rc.recipient = ctx.accounts.recipient.key();
        rc.amount_base_units = amount_base_units;
        rc.bump = ctx.bumps.claim_receipt;

        // Transfer the leaf amount from the vault (fees hard-zero — no deduction).
        let exp_key = exp.key();
        let va_bump = ctx.bumps.vault_authority;
        let signer: &[&[&[u8]]] = &[&[VAULT_AUTHORITY_SEED, exp_key.as_ref(), &[va_bump]]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.key(),
                Transfer {
                    from: ctx.accounts.vault.to_account_info(),
                    to: ctx.accounts.recipient_token.to_account_info(),
                    authority: ctx.accounts.vault_authority.to_account_info(),
                },
                signer,
            ),
            amount_base_units,
        )?;

        emit!(RewardClaimed {
            experiment: exp_key,
            leaf_index,
            recipient: ctx.accounts.recipient.key(),
            amount_base_units,
        });
        Ok(())
    }

    pub fn close_experiment(ctx: Context<CloseExperiment>) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let exp = &ctx.accounts.experiment;
        require!(exp.status == ExperimentStatus::Final, SettlementError::WrongStatus);
        require!(
            now >= ctx.accounts.distribution.claim_window_end,
            SettlementError::ClaimWindowNotElapsed
        );

        // Recover the entire remaining vault balance to the coordinator (funder).
        let remaining = ctx.accounts.vault.amount;
        if remaining > 0 {
            let exp_key = exp.key();
            let va_bump = ctx.bumps.vault_authority;
            let signer: &[&[&[u8]]] = &[&[VAULT_AUTHORITY_SEED, exp_key.as_ref(), &[va_bump]]];
            token::transfer(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.key(),
                    Transfer {
                        from: ctx.accounts.vault.to_account_info(),
                        to: ctx.accounts.recovery_token.to_account_info(),
                        authority: ctx.accounts.vault_authority.to_account_info(),
                    },
                    signer,
                ),
                remaining,
            )?;
        }

        // CPI: registry advances Final -> Closed (checks claim window elapsed).
        let bump = ctx.bumps.cpi_authority;
        let seeds: &[&[&[u8]]] = &[&[CPI_AUTHORITY_SEED, &[bump]]];
        experiment_registry::cpi::mark_closed(CpiContext::new_with_signer(
            ctx.accounts.experiment_registry_program.key(),
            experiment_registry::cpi::accounts::MarkBySettlement {
                protocol_config: ctx.accounts.protocol_config.to_account_info(),
                experiment: ctx.accounts.experiment.to_account_info(),
                caller_authority: ctx.accounts.cpi_authority.to_account_info(),
            },
            seeds,
        ))?;

        emit!(ExperimentClosed {
            experiment: exp.key(),
            recovered_base_units: remaining,
        });
        Ok(())
    }

    /// tx12 (state-machine v1.1, security finding H1): the bounded escape from the
    /// pre-`Final` fund trap. Returns the FULL experiment vault to `experiment.coordinator`
    /// and drives the experiment to `Closed` with `aborted = true` (via registry CPI).
    ///
    /// Reachable from any pre-`Final` state (`Frozen`/`Active`/`Evaluating`/`Challenged`),
    /// gated by EITHER a multisig threshold (signers in `remaining_accounts`) OR a
    /// permissionless timeout `now > evaluation_deadline + abort_grace_seconds`. It is
    /// structurally impossible after any claim (a `ClaimReceipt` only exists from `Final`,
    /// which abort cannot reach); the `Distribution`-does-not-exist assertion below makes
    /// that fact locally checkable rather than relying on reachability alone.
    ///
    /// Still-open `Challenge` bonds are escrowed under the CHALLENGE program's PDA authority
    /// and cannot be moved from here; they are refunded to their challengers permissionlessly
    /// via `challenge::refund_bond`, which is unlocked once `experiment.aborted == true`.
    pub fn abort_experiment(ctx: Context<AbortExperiment>) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let exp = &ctx.accounts.experiment;

        // Defensive: no Distribution (and therefore no ClaimReceipt) may exist. The PDA
        // account must be uninitialized. Structurally guaranteed pre-`Final`; asserted here.
        require!(
            ctx.accounts.distribution.data_is_empty(),
            SettlementError::DistributionExists
        );

        // Authorization: multisig threshold OR permissionless timeout.
        let timed_out = now
            > exp
                .evaluation_deadline
                .checked_add(ctx.accounts.protocol_config.abort_grace_seconds)
                .ok_or(SettlementError::MathOverflow)?;
        if !timed_out {
            experiment_registry::verify_multisig(
                ctx.remaining_accounts,
                &exp.authority_signers,
                exp.authority_threshold,
            )
            .map_err(|_| error!(SettlementError::AbortNotAuthorized))?;
        }

        // Return the full vault balance to the coordinator (funder). Pre-`Final` the vault
        // is untouched, so this is the entire budget.
        let recovered = ctx.accounts.vault.amount;
        if recovered > 0 {
            let exp_key = exp.key();
            let va_bump = ctx.bumps.vault_authority;
            let signer: &[&[&[u8]]] = &[&[VAULT_AUTHORITY_SEED, exp_key.as_ref(), &[va_bump]]];
            token::transfer(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.key(),
                    Transfer {
                        from: ctx.accounts.vault.to_account_info(),
                        to: ctx.accounts.recovery_token.to_account_info(),
                        authority: ctx.accounts.vault_authority.to_account_info(),
                    },
                    signer,
                ),
                recovered,
            )?;
        }

        // CPI: registry advances pre-`Final` -> Closed (aborted = true).
        let bump = ctx.bumps.cpi_authority;
        let seeds: &[&[&[u8]]] = &[&[CPI_AUTHORITY_SEED, &[bump]]];
        experiment_registry::cpi::mark_aborted(CpiContext::new_with_signer(
            ctx.accounts.experiment_registry_program.key(),
            experiment_registry::cpi::accounts::MarkBySettlement {
                protocol_config: ctx.accounts.protocol_config.to_account_info(),
                experiment: ctx.accounts.experiment.to_account_info(),
                caller_authority: ctx.accounts.cpi_authority.to_account_info(),
            },
            seeds,
        ))?;

        emit!(ExperimentAborted {
            experiment: ctx.accounts.experiment.key(),
            recovered_base_units: recovered,
            permissionless: timed_out,
        });
        Ok(())
    }
}

// ---------------- Accounts ----------------

#[derive(Accounts)]
pub struct SubmitEvaluation<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump, seeds::program = experiment_registry_program.key())]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    #[account(
        init_if_needed,
        payer = evaluator,
        space = Evaluation::SPACE,
        seeds = [b"evaluation", experiment.key().as_ref()],
        bump
    )]
    pub evaluation: Account<'info, Evaluation>,
    /// CHECK: epoch-0 EvidenceEpoch PDA; existence + owner verified in-handler.
    pub epoch_zero: UncheckedAccount<'info>,
    /// CHECK: settlement's CPI-authority PDA; signs the status CPI.
    #[account(seeds = [CPI_AUTHORITY_SEED], bump)]
    pub cpi_authority: UncheckedAccount<'info>,
    #[account(mut)]
    pub evaluator: Signer<'info>,
    pub experiment_registry_program: Program<'info, ExperimentRegistry>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct FinalizeDistribution<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump, seeds::program = experiment_registry_program.key())]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    #[account(seeds = [b"evaluation", experiment.key().as_ref()], bump = evaluation.bump, has_one = experiment @ SettlementError::WrongExperiment)]
    pub evaluation: Account<'info, Evaluation>,
    #[account(
        init,
        payer = finalizer,
        space = Distribution::SPACE,
        seeds = [b"distribution", experiment.key().as_ref()],
        bump
    )]
    pub distribution: Account<'info, Distribution>,
    /// CHECK: settlement's CPI-authority PDA; signs the status CPI.
    #[account(seeds = [CPI_AUTHORITY_SEED], bump)]
    pub cpi_authority: UncheckedAccount<'info>,
    #[account(mut)]
    pub finalizer: Signer<'info>,
    pub experiment_registry_program: Program<'info, ExperimentRegistry>,
    pub system_program: Program<'info, System>,
    // m-of-n multisig signers in remaining_accounts.
}

#[derive(Accounts)]
#[instruction(leaf_index: u64)]
pub struct ClaimReward<'info> {
    pub experiment: Account<'info, Experiment>,
    #[account(seeds = [b"distribution", experiment.key().as_ref()], bump = distribution.bump, has_one = experiment @ SettlementError::WrongExperiment)]
    pub distribution: Account<'info, Distribution>,
    #[account(
        init,
        payer = recipient,
        space = ClaimReceipt::SPACE,
        seeds = [b"claim", experiment.key().as_ref(), &leaf_index.to_le_bytes()],
        bump
    )]
    pub claim_receipt: Account<'info, ClaimReceipt>,
    #[account(mut, address = experiment.vault @ SettlementError::WrongVault)]
    pub vault: Account<'info, TokenAccount>,
    /// CHECK: settlement vault-authority PDA (token authority of the vault).
    #[account(seeds = [VAULT_AUTHORITY_SEED, experiment.key().as_ref()], bump)]
    pub vault_authority: UncheckedAccount<'info>,
    #[account(
        mut,
        constraint = recipient_token.mint == experiment.mint @ SettlementError::MintMismatch,
        constraint = recipient_token.owner == recipient.key() @ SettlementError::Unauthorized
    )]
    pub recipient_token: Account<'info, TokenAccount>,
    #[account(mut)]
    pub recipient: Signer<'info>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct CloseExperiment<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump, seeds::program = experiment_registry_program.key())]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    #[account(seeds = [b"distribution", experiment.key().as_ref()], bump = distribution.bump, has_one = experiment @ SettlementError::WrongExperiment)]
    pub distribution: Account<'info, Distribution>,
    #[account(mut, address = experiment.vault @ SettlementError::WrongVault)]
    pub vault: Account<'info, TokenAccount>,
    /// CHECK: settlement vault-authority PDA (token authority of the vault).
    #[account(seeds = [VAULT_AUTHORITY_SEED, experiment.key().as_ref()], bump)]
    pub vault_authority: UncheckedAccount<'info>,
    #[account(
        mut,
        constraint = recovery_token.mint == experiment.mint @ SettlementError::MintMismatch,
        constraint = recovery_token.owner == experiment.coordinator @ SettlementError::Unauthorized
    )]
    pub recovery_token: Account<'info, TokenAccount>,
    /// CHECK: settlement's CPI-authority PDA; signs the status CPI.
    #[account(seeds = [CPI_AUTHORITY_SEED], bump)]
    pub cpi_authority: UncheckedAccount<'info>,
    #[account(mut)]
    pub cranker: Signer<'info>,
    pub experiment_registry_program: Program<'info, ExperimentRegistry>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct AbortExperiment<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump, seeds::program = experiment_registry_program.key())]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    /// CHECK: the Distribution PDA. MUST be uninitialized (asserted in-handler): abort is
    /// only legal before any Distribution/ClaimReceipt exists.
    #[account(seeds = [b"distribution", experiment.key().as_ref()], bump)]
    pub distribution: UncheckedAccount<'info>,
    #[account(mut, address = experiment.vault @ SettlementError::WrongVault)]
    pub vault: Account<'info, TokenAccount>,
    /// CHECK: settlement vault-authority PDA (token authority of the vault).
    #[account(seeds = [VAULT_AUTHORITY_SEED, experiment.key().as_ref()], bump)]
    pub vault_authority: UncheckedAccount<'info>,
    #[account(
        mut,
        constraint = recovery_token.mint == experiment.mint @ SettlementError::MintMismatch,
        constraint = recovery_token.owner == experiment.coordinator @ SettlementError::Unauthorized
    )]
    pub recovery_token: Account<'info, TokenAccount>,
    /// CHECK: settlement's CPI-authority PDA; signs the status CPI.
    #[account(seeds = [CPI_AUTHORITY_SEED], bump)]
    pub cpi_authority: UncheckedAccount<'info>,
    #[account(mut)]
    pub cranker: Signer<'info>,
    pub experiment_registry_program: Program<'info, ExperimentRegistry>,
    pub token_program: Program<'info, Token>,
    // m-of-n multisig signers in remaining_accounts (only required on the non-timeout path).
}

// ---------------- State ----------------

#[account]
pub struct Evaluation {
    pub experiment: Pubkey,
    pub result_artifact_hash: [u8; 32],
    pub reward_root: [u8; 32],
    pub analysis_container_digest: [u8; 32],
    pub evaluator: Pubkey,
    pub bump: u8,
}
impl Evaluation {
    pub const SPACE: usize = 8 + 32 + 32 + 32 + 32 + 32 + 1;
}

#[account]
pub struct Distribution {
    pub experiment: Pubkey,
    pub reward_root: [u8; 32],
    pub total_allocated_base_units: u64,
    pub unallocated_base_units: u64,
    pub claim_window_end: i64,
    pub bump: u8,
}
impl Distribution {
    pub const SPACE: usize = 8 + 32 + 32 + 8 + 8 + 8 + 1;
}

/// Single-use nullifier for one reward leaf.
#[account]
pub struct ClaimReceipt {
    pub experiment: Pubkey,
    pub leaf_index: u64,
    pub recipient: Pubkey,
    pub amount_base_units: u64,
    pub bump: u8,
}
impl ClaimReceipt {
    pub const SPACE: usize = 8 + 32 + 8 + 32 + 8 + 1;
}

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct ClaimProofStep {
    pub sibling: [u8; 32],
    /// true => sibling is the LEFT node (self is the right child).
    pub sibling_is_left: bool,
}

// ---------------- Events ----------------

#[event]
pub struct EvaluationSubmitted {
    pub experiment: Pubkey,
    pub result_artifact_hash: [u8; 32],
    pub reward_root: [u8; 32],
    pub challenge_window_end: i64,
}

#[event]
pub struct DistributionFinalized {
    pub experiment: Pubkey,
    pub reward_root: [u8; 32],
    pub total_allocated_base_units: u64,
    pub unallocated_base_units: u64,
    pub claim_window_end: i64,
}

#[event]
pub struct RewardClaimed {
    pub experiment: Pubkey,
    pub leaf_index: u64,
    pub recipient: Pubkey,
    pub amount_base_units: u64,
}

#[event]
pub struct ExperimentClosed {
    pub experiment: Pubkey,
    pub recovered_base_units: u64,
}

#[event]
pub struct ExperimentAborted {
    pub experiment: Pubkey,
    pub recovered_base_units: u64,
    /// true if taken via the permissionless timeout path, false if via multisig.
    pub permissionless: bool,
}

// ---------------- Errors ----------------

#[error_code]
pub enum SettlementError {
    #[msg("Experiment is not in the required status")]
    WrongStatus,
    #[msg("Signer not authorized")]
    Unauthorized,
    #[msg("Seed has not been revealed")]
    SeedNotRevealed,
    #[msg("Active window has not ended")]
    ActiveWindowNotEnded,
    #[msg("Evaluation deadline has passed")]
    EvaluationDeadlinePassed,
    #[msg("Echoed analysis_container_digest does not match the frozen one")]
    ContainerDigestMismatch,
    #[msg("No evidence epoch exists")]
    NoEvidence,
    #[msg("Multisig threshold not met")]
    MultisigThresholdNotMet,
    #[msg("Allocation exceeds budget")]
    AllocationExceedsBudget,
    #[msg("Merkle proof of the reward leaf is invalid")]
    InvalidMerkleProof,
    #[msg("Claim window is closed")]
    ClaimWindowClosed,
    #[msg("Claim window has not elapsed")]
    ClaimWindowNotElapsed,
    #[msg("Vault does not match experiment")]
    WrongVault,
    #[msg("Evaluation/Distribution does not belong to this experiment")]
    WrongExperiment,
    #[msg("Token mint mismatch")]
    MintMismatch,
    #[msg("Checked arithmetic overflow")]
    MathOverflow,
    #[msg("A Distribution already exists; abort is only legal before finalize")]
    DistributionExists,
    #[msg("abort_experiment not authorized: multisig threshold not met and timeout not elapsed")]
    AbortNotAuthorized,
}
