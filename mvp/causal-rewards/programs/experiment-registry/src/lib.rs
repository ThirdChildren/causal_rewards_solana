//! experiment-registry — owns `ProtocolConfig`, `Experiment`, `CohortSet`.
//!
//! Enforces freeze-before-reveal STRUCTURALLY (Invariant 1):
//!   * `create_experiment` stores the seed *commitment* only — there is no field to
//!     hold a raw seed.
//!   * `freeze_experiment` records the manifest hash and locks the immutability set;
//!     no later instruction writes any frozen field.
//!   * `publish_cohort_root` commits the assignment BEFORE the seed is revealed.
//!   * `reveal_seed` recomputes `sha256("CRP-seed-commit-v1"||seed)` and REJECTS if it
//!     does not equal the stored commitment, and only runs in `Active` after publish.
//!
//! `Experiment.status` is written ONLY by this program. Satellite programs advance it
//! via CPI (`mark_*`), authenticated by a program-authority PDA (`seeds::program`).

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

pub mod error;
pub mod events;
pub mod state;

use error::RegistryError;
use events::*;
use state::*;

declare_id!("8DotPgXajgeHt68htC7vbuvScUDkQa9ZPi3a5Sk1mioj");

pub const CPI_AUTHORITY_SEED: &[u8] = b"cpi_authority";

#[program]
pub mod experiment_registry {
    use super::*;

    pub fn init_protocol_config(
        ctx: Context<InitProtocolConfig>,
        schema_version: u16,
        evidence_program: Pubkey,
        settlement_program: Pubkey,
        challenge_program: Pubkey,
        abort_grace_seconds: i64,
    ) -> Result<()> {
        require!(abort_grace_seconds >= 0, RegistryError::InvalidWindowOrdering);
        let cfg = &mut ctx.accounts.protocol_config;
        cfg.admin = ctx.accounts.admin.key();
        cfg.fee_bps = 0; // hard-zero fee (Invariant 7)
        require!(cfg.fee_bps == 0, RegistryError::FeeNotZero);
        cfg.paused = false;
        cfg.cluster = CLUSTER_DEVNET; // devnet only (Invariant 7)
        cfg.schema_version = schema_version;
        cfg.evidence_program = evidence_program;
        cfg.settlement_program = settlement_program;
        cfg.challenge_program = challenge_program;
        cfg.abort_grace_seconds = abort_grace_seconds;
        cfg.bump = ctx.bumps.protocol_config;

        emit!(ProtocolInitialized {
            admin: cfg.admin,
            schema_version,
        });
        Ok(())
    }

    /// Emergency pause / unpause. Admin only. Cannot rewrite any frozen record — it
    /// merely blocks advancing instructions (Invariant: constrained authority).
    pub fn set_paused(ctx: Context<AdminOnly>, paused: bool) -> Result<()> {
        ctx.accounts.protocol_config.paused = paused;
        Ok(())
    }

    pub fn create_experiment(
        ctx: Context<CreateExperiment>,
        experiment_id_hash: [u8; 32],
        args: CreateExperimentArgs,
    ) -> Result<()> {
        let cfg = &ctx.accounts.protocol_config;
        require!(cfg.cluster == CLUSTER_DEVNET, RegistryError::NotDevnet);
        require!(cfg.fee_bps == 0, RegistryError::FeeNotZero);
        require!(!cfg.paused, RegistryError::Paused);

        // experiment_id well-formed + binds the PDA seed.
        let id_bytes = args.experiment_id.as_bytes();
        require!(
            !id_bytes.is_empty() && id_bytes.len() <= MAX_EXPERIMENT_ID_LEN,
            RegistryError::InvalidExperimentId
        );
        let expected_hash = crp_crypto::sha256v(&[b"CRP-exp-id", id_bytes]);
        require!(expected_hash == experiment_id_hash, RegistryError::InvalidExperimentId);

        // multisig well-formed.
        let n = args.authority_signers.len();
        require!(n >= 1 && n <= MAX_SIGNERS, RegistryError::InvalidMultisig);
        require!(
            args.authority_threshold >= 1 && (args.authority_threshold as usize) <= n,
            RegistryError::InvalidThreshold
        );

        // window ordering (state-machine transition 1).
        require!(
            args.active_start <= args.active_end && args.active_end <= args.evaluation_deadline,
            RegistryError::InvalidWindowOrdering
        );
        require!(
            args.challenge_window_seconds >= 0 && args.claim_window_seconds >= 0,
            RegistryError::InvalidWindowOrdering
        );
        let now = Clock::get()?.unix_timestamp;
        require!(args.freeze_by >= now, RegistryError::FreezeDeadlinePassed);

        // Fund the vault with the budget (pull from coordinator's funding account).
        require!(
            ctx.accounts.mint.key() == ctx.accounts.coordinator_funding.mint,
            RegistryError::MintMismatch
        );
        // The vault's authority is the settlement program's per-experiment PDA, so the
        // settlement program (and only it) can move funds out at claim/close time.
        let (expected_vault_authority, _) = Pubkey::find_program_address(
            &[b"vault_authority", ctx.accounts.experiment.key().as_ref()],
            &cfg.settlement_program,
        );
        require_keys_eq!(
            ctx.accounts.vault_authority.key(),
            expected_vault_authority,
            RegistryError::Unauthorized
        );
        if args.budget_base_units > 0 {
            token::transfer(
                CpiContext::new(
                    ctx.accounts.token_program.key(),
                    Transfer {
                        from: ctx.accounts.coordinator_funding.to_account_info(),
                        to: ctx.accounts.vault.to_account_info(),
                        authority: ctx.accounts.coordinator.to_account_info(),
                    },
                ),
                args.budget_base_units,
            )?;
        }

        let exp = &mut ctx.accounts.experiment;
        exp.status = ExperimentStatus::Draft;
        exp.coordinator = ctx.accounts.coordinator.key();
        exp.evaluator = args.evaluator;
        exp.authority_threshold = args.authority_threshold;
        exp.authority_signers = args.authority_signers;
        exp.experiment_id = args.experiment_id.clone();
        exp.manifest_hash = [0u8; 32]; // recorded at freeze
        exp.analysis_container_digest = args.analysis_container_digest;
        exp.reward_curve_hash = args.reward_curve_hash;
        exp.seed_commitment = args.seed_commitment;
        exp.mint = ctx.accounts.mint.key();
        exp.vault = ctx.accounts.vault.key();
        exp.budget_base_units = args.budget_base_units;
        exp.challenge_bond_base_units = args.challenge_bond_base_units;
        exp.freeze_by = args.freeze_by;
        exp.active_start = args.active_start;
        exp.active_end = args.active_end;
        exp.evaluation_deadline = args.evaluation_deadline;
        exp.challenge_window_seconds = args.challenge_window_seconds;
        exp.claim_window_seconds = args.claim_window_seconds;
        exp.cohort_published = false;
        exp.revealed_seed = None;
        exp.evaluation_valid = false;
        exp.open_challenges = 0;
        exp.challenge_window_end = 0;
        exp.claim_window_end = 0;
        exp.aborted = false;
        exp.created_at = now;
        exp.bump = ctx.bumps.experiment;
        exp.vault_bump = ctx.bumps.vault;

        emit!(ExperimentCreated {
            experiment: exp.key(),
            experiment_id: exp.experiment_id.clone(),
            coordinator: exp.coordinator,
            evaluator: exp.evaluator,
            seed_commitment: exp.seed_commitment,
            budget_base_units: exp.budget_base_units,
        });
        Ok(())
    }

    /// Freeze: record the manifest hash and lock the immutability set. Multisig only.
    pub fn freeze_experiment(ctx: Context<FreezeExperiment>, manifest_hash: [u8; 32]) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        let now = Clock::get()?.unix_timestamp;
        {
            let exp = &ctx.accounts.experiment;
            require!(exp.status == ExperimentStatus::Draft, RegistryError::WrongStatus);
            require!(now <= exp.freeze_by, RegistryError::FreezeWindowClosed);
            verify_multisig(
                ctx.remaining_accounts,
                &exp.authority_signers,
                exp.authority_threshold,
            )?;
        }
        let exp = &mut ctx.accounts.experiment;
        exp.manifest_hash = manifest_hash;
        exp.status = ExperimentStatus::Frozen;

        emit!(ExperimentFrozen {
            experiment: exp.key(),
            manifest_hash,
        });
        Ok(())
    }

    /// Publish the assignment/cohort Merkle root. Coordinator only. Frozen -> Active.
    /// Commits the assignment BEFORE the seed can be revealed (freeze-before-reveal).
    pub fn publish_cohort_root(
        ctx: Context<PublishCohortRoot>,
        cohort_root: [u8; 32],
        cohort_count: u32,
    ) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        {
            let exp = &ctx.accounts.experiment;
            require!(exp.status == ExperimentStatus::Frozen, RegistryError::WrongStatus);
            require!(!exp.cohort_published, RegistryError::CohortAlreadyPublished);
            require!(
                exp.revealed_seed.is_none(),
                RegistryError::SeedAlreadyRevealed
            );
            require_keys_eq!(
                ctx.accounts.coordinator.key(),
                exp.coordinator,
                RegistryError::Unauthorized
            );
        }
        let cs = &mut ctx.accounts.cohort_set;
        cs.experiment = ctx.accounts.experiment.key();
        cs.cohort_root = cohort_root;
        cs.cohort_count = cohort_count;
        cs.bump = ctx.bumps.cohort_set;

        let exp = &mut ctx.accounts.experiment;
        exp.cohort_published = true;
        exp.status = ExperimentStatus::Active;

        emit!(CohortRootPublished {
            experiment: exp.key(),
            cohort_root,
            cohort_count,
        });
        Ok(())
    }

    /// Reveal the seed. Coordinator only. Verifies the commitment on-chain (Invariant 1).
    pub fn reveal_seed(ctx: Context<RevealSeed>, seed: [u8; 32]) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        let exp = &mut ctx.accounts.experiment;
        require!(exp.status == ExperimentStatus::Active, RegistryError::WrongStatus);
        require!(exp.cohort_published, RegistryError::CohortNotPublished);
        require!(exp.revealed_seed.is_none(), RegistryError::SeedAlreadyRevealed);
        require_keys_eq!(
            ctx.accounts.coordinator.key(),
            exp.coordinator,
            RegistryError::Unauthorized
        );

        // Recompute the commitment from the revealed seed and reject on mismatch.
        let computed = crp_crypto::seed_commitment(&seed);
        require!(
            computed == exp.seed_commitment,
            RegistryError::SeedCommitmentMismatch
        );

        exp.revealed_seed = Some(seed);

        emit!(SeedRevealed {
            experiment: exp.key(),
            seed_commitment: exp.seed_commitment,
            revealed_seed: seed,
        });
        Ok(())
    }

    // ---------------- CPI-only status transitions ----------------

    /// tx6: Active -> Evaluating (first submission) or Evaluating -> Evaluating
    /// (corrected re-submission after an upheld challenge). Settlement only.
    ///
    /// Writes the ABSOLUTE `challenge_window_end` once here (never derived elsewhere,
    /// so no earlier event can shorten it — security finding M1), sets
    /// `evaluation_valid = true`, and re-initializes `open_challenges = 0`.
    pub fn mark_evaluating(ctx: Context<MarkBySettlement>, challenge_window_end: i64) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        let exp = &mut ctx.accounts.experiment;
        let from = exp.status;
        // Active (first submit) OR Evaluating self-loop only to replace an
        // invalidated evaluation once all challenges are resolved (state-machine tx6).
        let ok = matches!(from, ExperimentStatus::Active)
            || (matches!(from, ExperimentStatus::Evaluating)
                && !exp.evaluation_valid
                && exp.open_challenges == 0);
        require!(ok, RegistryError::WrongStatus);
        exp.status = ExperimentStatus::Evaluating;
        exp.evaluation_valid = true;
        exp.open_challenges = 0;
        exp.challenge_window_end = challenge_window_end;
        emit_transition(exp.key(), from, exp.status, ctx.accounts.protocol_config.settlement_program);
        Ok(())
    }

    /// tx7: Evaluating|Challenged -> Challenged; increments open_challenges. Challenge only.
    pub fn mark_challenged(ctx: Context<MarkByChallenge>) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        let exp = &mut ctx.accounts.experiment;
        let from = exp.status;
        require!(
            matches!(from, ExperimentStatus::Evaluating | ExperimentStatus::Challenged),
            RegistryError::WrongStatus
        );
        require!(exp.evaluation_valid, RegistryError::EvaluationNotValid);
        exp.open_challenges = exp.open_challenges.checked_add(1).ok_or(RegistryError::MathOverflow)?;
        exp.status = ExperimentStatus::Challenged;
        emit_transition(exp.key(), from, exp.status, ctx.accounts.protocol_config.challenge_program);
        Ok(())
    }

    /// tx8: resolve exactly ONE challenge as UPHELD. Challenge only.
    ///
    /// `open_challenges` is the SOLE gate for leaving `Challenged` (security finding H2):
    /// this decrements the counter by 1 and sets `evaluation_valid = false` (an upheld
    /// resolution invalidates the evaluation regardless of order). State returns to
    /// `Evaluating` only when `open_challenges` reaches 0; otherwise it stays `Challenged`
    /// and every remaining challenge is still independently resolvable.
    pub fn resolve_upheld(ctx: Context<MarkByChallenge>) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        let exp = &mut ctx.accounts.experiment;
        let from = exp.status;
        require!(matches!(from, ExperimentStatus::Challenged), RegistryError::WrongStatus);
        exp.open_challenges = exp.open_challenges.checked_sub(1).ok_or(RegistryError::MathOverflow)?;
        exp.evaluation_valid = false;
        if exp.open_challenges == 0 {
            exp.status = ExperimentStatus::Evaluating;
        }
        emit_transition(exp.key(), from, exp.status, ctx.accounts.protocol_config.challenge_program);
        Ok(())
    }

    /// tx8: resolve exactly ONE challenge as DISMISSED. Challenge only.
    ///
    /// Decrements `open_challenges` by 1 and leaves `evaluation_valid` untouched. State
    /// returns to `Evaluating` only when `open_challenges` reaches 0 (security finding H2);
    /// a dismissed challenge NEVER shortcuts the finalize window for a not-yet-opened
    /// honest challenge (security finding M1 — there is no `ever_challenged` flag).
    pub fn resolve_dismissed(ctx: Context<MarkByChallenge>) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        let exp = &mut ctx.accounts.experiment;
        let from = exp.status;
        require!(matches!(from, ExperimentStatus::Challenged), RegistryError::WrongStatus);
        exp.open_challenges = exp.open_challenges.checked_sub(1).ok_or(RegistryError::MathOverflow)?;
        if exp.open_challenges == 0 {
            exp.status = ExperimentStatus::Evaluating;
        }
        emit_transition(exp.key(), from, exp.status, ctx.accounts.protocol_config.challenge_program);
        Ok(())
    }

    /// tx9: Evaluating -> Final. Settlement only.
    ///
    /// Guard (security finding M1): finalize is taken ONLY from `Evaluating` and requires
    /// the conjunction `now >= challenge_window_end AND open_challenges == 0 AND
    /// evaluation_valid`. There is no `ever_challenged` short-circuit.
    pub fn mark_final(ctx: Context<MarkBySettlement>, claim_window_end: i64) -> Result<()> {
        require!(!ctx.accounts.protocol_config.paused, RegistryError::Paused);
        let now = Clock::get()?.unix_timestamp;
        let exp = &mut ctx.accounts.experiment;
        let from = exp.status;
        require!(matches!(from, ExperimentStatus::Evaluating), RegistryError::WrongStatus);
        require!(exp.evaluation_valid, RegistryError::EvaluationNotValid);
        require!(exp.open_challenges == 0, RegistryError::OpenChallengesRemain);
        require!(now >= exp.challenge_window_end, RegistryError::ChallengeWindowNotElapsed);
        exp.status = ExperimentStatus::Final;
        exp.claim_window_end = claim_window_end;
        emit_transition(exp.key(), from, exp.status, ctx.accounts.protocol_config.settlement_program);
        Ok(())
    }

    /// tx12: {Frozen,Active,Evaluating,Challenged} -> Closed (`aborted = true`). Settlement only.
    ///
    /// The authorization gate (multisig OR permissionless timeout) and the vault return +
    /// still-open-bond refunds live in the settlement/challenge programs; this transition
    /// enforces only the legal status set and stamps the `aborted` marker. NOT gated on
    /// `paused` — abort is the bounded escape from the pre-`Final` fund trap (H1) and must
    /// remain reachable so funds can never be trapped by pausing.
    pub fn mark_aborted(ctx: Context<MarkBySettlement>) -> Result<()> {
        let exp = &mut ctx.accounts.experiment;
        let from = exp.status;
        require!(
            matches!(
                from,
                ExperimentStatus::Frozen
                    | ExperimentStatus::Active
                    | ExperimentStatus::Evaluating
                    | ExperimentStatus::Challenged
            ),
            RegistryError::AbortNotAllowed
        );
        require!(!exp.aborted, RegistryError::AlreadyAborted);
        exp.aborted = true;
        exp.status = ExperimentStatus::Closed;
        emit_transition(exp.key(), from, exp.status, ctx.accounts.protocol_config.settlement_program);
        emit!(ExperimentAborted {
            experiment: exp.key(),
            from: from as u8,
            open_challenges: exp.open_challenges,
        });
        Ok(())
    }

    /// Final -> Closed. Settlement only.
    pub fn mark_closed(ctx: Context<MarkBySettlement>) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let exp = &mut ctx.accounts.experiment;
        let from = exp.status;
        require!(matches!(from, ExperimentStatus::Final), RegistryError::WrongStatus);
        require!(now >= exp.claim_window_end, RegistryError::ClaimWindowNotElapsed);
        exp.status = ExperimentStatus::Closed;
        emit_transition(exp.key(), from, exp.status, ctx.accounts.protocol_config.settlement_program);
        Ok(())
    }
}

fn emit_transition(
    experiment: Pubkey,
    from: ExperimentStatus,
    to: ExperimentStatus,
    caller_program: Pubkey,
) {
    emit!(StatusTransitioned {
        experiment,
        from: from as u8,
        to: to as u8,
        caller_program,
    });
}

/// m-of-n multisig check: >= threshold DISTINCT signers, each present in `signers`.
pub fn verify_multisig(
    provided: &[AccountInfo],
    signers: &[Pubkey],
    threshold: u8,
) -> Result<()> {
    let mut counted: Vec<Pubkey> = Vec::new();
    for ai in provided.iter() {
        if !ai.is_signer {
            continue;
        }
        let k = ai.key();
        if signers.contains(&k) && !counted.contains(&k) {
            counted.push(k);
        }
    }
    require!(
        counted.len() >= threshold as usize,
        RegistryError::MultisigThresholdNotMet
    );
    Ok(())
}

// ---------------- Args ----------------

#[derive(AnchorSerialize, AnchorDeserialize, Clone)]
pub struct CreateExperimentArgs {
    pub experiment_id: String,
    pub evaluator: Pubkey,
    pub authority_threshold: u8,
    pub authority_signers: Vec<Pubkey>,
    pub analysis_container_digest: [u8; 32],
    pub reward_curve_hash: [u8; 32],
    pub seed_commitment: [u8; 32],
    pub budget_base_units: u64,
    pub challenge_bond_base_units: u64,
    pub freeze_by: i64,
    pub active_start: i64,
    pub active_end: i64,
    pub evaluation_deadline: i64,
    pub challenge_window_seconds: i64,
    pub claim_window_seconds: i64,
}

// ---------------- Account contexts ----------------

#[derive(Accounts)]
pub struct InitProtocolConfig<'info> {
    #[account(
        init,
        payer = admin,
        space = ProtocolConfig::SPACE,
        seeds = [b"protocol_config"],
        bump
    )]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct AdminOnly<'info> {
    #[account(
        mut,
        seeds = [b"protocol_config"],
        bump = protocol_config.bump,
        has_one = admin @ RegistryError::Unauthorized
    )]
    pub protocol_config: Account<'info, ProtocolConfig>,
    pub admin: Signer<'info>,
}

#[derive(Accounts)]
#[instruction(experiment_id_hash: [u8; 32])]
pub struct CreateExperiment<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump)]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(
        init,
        payer = coordinator,
        space = Experiment::SPACE,
        seeds = [b"experiment", experiment_id_hash.as_ref()],
        bump
    )]
    pub experiment: Account<'info, Experiment>,
    #[account(
        init,
        payer = coordinator,
        seeds = [b"vault", experiment.key().as_ref()],
        bump,
        token::mint = mint,
        token::authority = vault_authority
    )]
    pub vault: Account<'info, TokenAccount>,
    /// CHECK: settlement program's per-experiment vault-authority PDA; verified in-handler.
    pub vault_authority: UncheckedAccount<'info>,
    pub mint: Account<'info, Mint>,
    #[account(mut, constraint = coordinator_funding.owner == coordinator.key() @ RegistryError::Unauthorized)]
    pub coordinator_funding: Account<'info, TokenAccount>,
    #[account(mut)]
    pub coordinator: Signer<'info>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct FreezeExperiment<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump)]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    // m-of-n multisig signers are passed in remaining_accounts.
}

#[derive(Accounts)]
pub struct PublishCohortRoot<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump)]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    #[account(
        init,
        payer = coordinator,
        space = CohortSet::SPACE,
        seeds = [b"cohort_set", experiment.key().as_ref()],
        bump
    )]
    pub cohort_set: Account<'info, CohortSet>,
    #[account(mut)]
    pub coordinator: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RevealSeed<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump)]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    pub coordinator: Signer<'info>,
}

#[derive(Accounts)]
pub struct MarkBySettlement<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump)]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    /// Authorizes the caller: PDA of the SETTLEMENT program signs this CPI.
    #[account(
        seeds = [CPI_AUTHORITY_SEED],
        bump,
        seeds::program = protocol_config.settlement_program
    )]
    pub caller_authority: Signer<'info>,
}

#[derive(Accounts)]
pub struct MarkByChallenge<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump)]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    /// Authorizes the caller: PDA of the CHALLENGE program signs this CPI.
    #[account(
        seeds = [CPI_AUTHORITY_SEED],
        bump,
        seeds::program = protocol_config.challenge_program
    )]
    pub caller_authority: Signer<'info>,
}
