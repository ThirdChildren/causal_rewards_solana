//! challenge — owns `Challenge`. Opens a bonded challenge that pauses finality and
//! resolves it per the frozen policy.
//!
//! * `open_challenge` escrows a bond (>= frozen `challenge_bond_base_units`) and CPIs
//!   the registry Evaluating|Challenged -> Challenged. Griefing has a per-attempt cost.
//! * `resolve_challenge` (multisig) sets the resolution and either returns the bond
//!   (upheld -> evaluation invalidated, back to Evaluating) or forfeits it to the
//!   coordinator (dismissed). Only an upheld, verifier-backed challenge invalidates.

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};
use experiment_registry::program::ExperimentRegistry;
use experiment_registry::state::{Experiment, ExperimentStatus, ProtocolConfig};

declare_id!("J9MfPYVhveHLLRnGBUiMxJqCLJP6s5ZUn7e5h3mnsG4z");

pub const CPI_AUTHORITY_SEED: &[u8] = b"cpi_authority";

pub const RESOLUTION_UNSET: u8 = 0;
pub const RESOLUTION_UPHELD: u8 = 1;
pub const RESOLUTION_DISMISSED: u8 = 2;

#[program]
pub mod challenge {
    use super::*;

    pub fn open_challenge(ctx: Context<OpenChallenge>, reason_code: u16, bond_amount: u64) -> Result<()> {
        let now = Clock::get()?.unix_timestamp;
        let exp = &ctx.accounts.experiment;
        require!(
            matches!(exp.status, ExperimentStatus::Evaluating | ExperimentStatus::Challenged),
            ChallengeError::WrongStatus
        );
        require!(exp.evaluation_present && !exp.evaluation_invalidated, ChallengeError::NoLiveEvaluation);
        require!(now <= exp.challenge_window_end, ChallengeError::ChallengeWindowClosed);
        require!(
            bond_amount >= exp.challenge_bond_base_units,
            ChallengeError::BondTooLow
        );

        // Escrow the bond into the per-challenge bond vault.
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.key(),
                Transfer {
                    from: ctx.accounts.challenger_token.to_account_info(),
                    to: ctx.accounts.bond_vault.to_account_info(),
                    authority: ctx.accounts.challenger.to_account_info(),
                },
            ),
            bond_amount,
        )?;

        let ch = &mut ctx.accounts.challenge;
        ch.experiment = exp.key();
        ch.challenger = ctx.accounts.challenger.key();
        ch.bond_amount = bond_amount;
        ch.reason_code = reason_code;
        ch.resolution = RESOLUTION_UNSET;
        ch.bond_vault = ctx.accounts.bond_vault.key();
        ch.bump = ctx.bumps.challenge;

        // CPI: registry -> Challenged (increments open_challenges).
        let bump = ctx.bumps.cpi_authority;
        let seeds: &[&[&[u8]]] = &[&[CPI_AUTHORITY_SEED, &[bump]]];
        experiment_registry::cpi::mark_challenged(CpiContext::new_with_signer(
            ctx.accounts.experiment_registry_program.key(),
            experiment_registry::cpi::accounts::MarkByChallenge {
                protocol_config: ctx.accounts.protocol_config.to_account_info(),
                experiment: ctx.accounts.experiment.to_account_info(),
                caller_authority: ctx.accounts.cpi_authority.to_account_info(),
            },
            seeds,
        ))?;

        emit!(ChallengeOpened {
            experiment: exp.key(),
            challenger: ch.challenger,
            reason_code,
            bond_amount,
        });
        Ok(())
    }

    /// Resolve a challenge. Multisig-gated. `upheld = true` invalidates the evaluation
    /// and returns the bond; `upheld = false` dismisses and forfeits the bond.
    pub fn resolve_challenge(ctx: Context<ResolveChallenge>, upheld: bool) -> Result<()> {
        let exp = &ctx.accounts.experiment;
        require!(exp.status == ExperimentStatus::Challenged, ChallengeError::WrongStatus);
        require!(
            ctx.accounts.challenge.resolution == RESOLUTION_UNSET,
            ChallengeError::AlreadyResolved
        );

        // Multisig gate.
        experiment_registry::verify_multisig(
            ctx.remaining_accounts,
            &exp.authority_signers,
            exp.authority_threshold,
        )
        .map_err(|_| error!(ChallengeError::MultisigThresholdNotMet))?;

        // Bond destination correctness by resolution outcome.
        if upheld {
            require_keys_eq!(
                ctx.accounts.bond_destination.owner,
                ctx.accounts.challenge.challenger,
                ChallengeError::WrongBondDestination
            );
        } else {
            require_keys_eq!(
                ctx.accounts.bond_destination.owner,
                exp.coordinator,
                ChallengeError::WrongBondDestination
            );
        }

        // Move the escrowed bond (returned on upheld, forfeited on dismissed).
        let amount = ctx.accounts.bond_vault.amount;
        if amount > 0 {
            let exp_key = exp.key();
            let challenger = ctx.accounts.challenge.challenger;
            let ch_bump = ctx.accounts.challenge.bump;
            let signer: &[&[&[u8]]] =
                &[&[b"challenge", exp_key.as_ref(), challenger.as_ref(), &[ch_bump]]];
            token::transfer(
                CpiContext::new_with_signer(
                    ctx.accounts.token_program.key(),
                    Transfer {
                        from: ctx.accounts.bond_vault.to_account_info(),
                        to: ctx.accounts.bond_destination.to_account_info(),
                        authority: ctx.accounts.challenge.to_account_info(),
                    },
                    signer,
                ),
                amount,
            )?;
        }

        ctx.accounts.challenge.resolution = if upheld {
            RESOLUTION_UPHELD
        } else {
            RESOLUTION_DISMISSED
        };

        // CPI: registry status change.
        let bump = ctx.bumps.cpi_authority;
        let seeds: &[&[&[u8]]] = &[&[CPI_AUTHORITY_SEED, &[bump]]];
        let cpi_accounts = experiment_registry::cpi::accounts::MarkByChallenge {
            protocol_config: ctx.accounts.protocol_config.to_account_info(),
            experiment: ctx.accounts.experiment.to_account_info(),
            caller_authority: ctx.accounts.cpi_authority.to_account_info(),
        };
        let cpi_program = ctx.accounts.experiment_registry_program.key();
        if upheld {
            experiment_registry::cpi::resolve_upheld(CpiContext::new_with_signer(
                cpi_program,
                cpi_accounts,
                seeds,
            ))?;
        } else {
            experiment_registry::cpi::resolve_dismissed(CpiContext::new_with_signer(
                cpi_program,
                cpi_accounts,
                seeds,
            ))?;
        }

        emit!(ChallengeResolved {
            experiment: exp.key(),
            challenger: ctx.accounts.challenge.challenger,
            upheld,
        });
        Ok(())
    }
}

#[derive(Accounts)]
pub struct OpenChallenge<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump, seeds::program = experiment_registry_program.key())]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Box<Account<'info, Experiment>>,
    #[account(
        init,
        payer = challenger,
        space = Challenge::SPACE,
        seeds = [b"challenge", experiment.key().as_ref(), challenger.key().as_ref()],
        bump
    )]
    pub challenge: Box<Account<'info, Challenge>>,
    #[account(
        init,
        payer = challenger,
        seeds = [b"bond_vault", challenge.key().as_ref()],
        bump,
        token::mint = mint,
        token::authority = challenge
    )]
    pub bond_vault: Box<Account<'info, TokenAccount>>,
    #[account(address = experiment.mint @ ChallengeError::MintMismatch)]
    pub mint: Box<Account<'info, Mint>>,
    #[account(
        mut,
        constraint = challenger_token.mint == experiment.mint @ ChallengeError::MintMismatch,
        constraint = challenger_token.owner == challenger.key() @ ChallengeError::Unauthorized
    )]
    pub challenger_token: Box<Account<'info, TokenAccount>>,
    /// CHECK: challenge program's CPI-authority PDA; signs the status CPI.
    #[account(seeds = [CPI_AUTHORITY_SEED], bump)]
    pub cpi_authority: UncheckedAccount<'info>,
    #[account(mut)]
    pub challenger: Signer<'info>,
    pub experiment_registry_program: Program<'info, ExperimentRegistry>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
}

#[derive(Accounts)]
pub struct ResolveChallenge<'info> {
    #[account(seeds = [b"protocol_config"], bump = protocol_config.bump, seeds::program = experiment_registry_program.key())]
    pub protocol_config: Account<'info, ProtocolConfig>,
    #[account(mut)]
    pub experiment: Account<'info, Experiment>,
    #[account(
        mut,
        seeds = [b"challenge", experiment.key().as_ref(), challenge.challenger.as_ref()],
        bump = challenge.bump,
        has_one = experiment @ ChallengeError::WrongExperiment
    )]
    pub challenge: Account<'info, Challenge>,
    #[account(mut, address = challenge.bond_vault @ ChallengeError::WrongBondVault)]
    pub bond_vault: Account<'info, TokenAccount>,
    #[account(mut, constraint = bond_destination.mint == experiment.mint @ ChallengeError::MintMismatch)]
    pub bond_destination: Account<'info, TokenAccount>,
    /// CHECK: challenge program's CPI-authority PDA; signs the status CPI.
    #[account(seeds = [CPI_AUTHORITY_SEED], bump)]
    pub cpi_authority: UncheckedAccount<'info>,
    #[account(mut)]
    pub resolver: Signer<'info>,
    pub experiment_registry_program: Program<'info, ExperimentRegistry>,
    pub token_program: Program<'info, Token>,
    // m-of-n multisig signers in remaining_accounts.
}

#[account]
pub struct Challenge {
    pub experiment: Pubkey,
    pub challenger: Pubkey,
    pub bond_amount: u64,
    pub reason_code: u16,
    pub resolution: u8,
    pub bond_vault: Pubkey,
    pub bump: u8,
}
impl Challenge {
    pub const SPACE: usize = 8 + 32 + 32 + 8 + 2 + 1 + 32 + 1;
}

#[event]
pub struct ChallengeOpened {
    pub experiment: Pubkey,
    pub challenger: Pubkey,
    pub reason_code: u16,
    pub bond_amount: u64,
}

#[event]
pub struct ChallengeResolved {
    pub experiment: Pubkey,
    pub challenger: Pubkey,
    pub upheld: bool,
}

#[error_code]
pub enum ChallengeError {
    #[msg("Experiment is not in the required status")]
    WrongStatus,
    #[msg("No live evaluation to challenge")]
    NoLiveEvaluation,
    #[msg("Challenge window is closed")]
    ChallengeWindowClosed,
    #[msg("Bond is below the required minimum")]
    BondTooLow,
    #[msg("Challenge already resolved")]
    AlreadyResolved,
    #[msg("Multisig threshold not met")]
    MultisigThresholdNotMet,
    #[msg("Bond destination owner is wrong for this resolution")]
    WrongBondDestination,
    #[msg("Bond vault does not match challenge")]
    WrongBondVault,
    #[msg("Challenge does not belong to this experiment")]
    WrongExperiment,
    #[msg("Signer not authorized")]
    Unauthorized,
    #[msg("Token mint mismatch")]
    MintMismatch,
}
