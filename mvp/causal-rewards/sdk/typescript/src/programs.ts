/**
 * On-chain program IDs (the `address` field of each IDL) and canonical PDA seeds.
 * These are the stable, deployed addresses from `Anchor.toml` / the IDLs.
 */

import { PublicKey } from "@solana/web3.js";

import experimentRegistryIdl from "./idl/experiment_registry.json";
import evidenceRegistryIdl from "./idl/evidence_registry.json";
import settlementIdl from "./idl/settlement.json";
import challengeIdl from "./idl/challenge.json";

export const EXPERIMENT_REGISTRY_PROGRAM_ID = new PublicKey(experimentRegistryIdl.address);
export const EVIDENCE_REGISTRY_PROGRAM_ID = new PublicKey(evidenceRegistryIdl.address);
export const SETTLEMENT_PROGRAM_ID = new PublicKey(settlementIdl.address);
export const CHALLENGE_PROGRAM_ID = new PublicKey(challengeIdl.address);

/** SPL Token program (classic), as pinned in the IDLs. */
export const TOKEN_PROGRAM_ID = new PublicKey("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA");

const ENC = new TextEncoder();
const seed = (s: string) => ENC.encode(s);

/** Canonical PDA seed byte strings (must match the on-chain `#[account(seeds=...)]`). */
export const SEEDS = {
  protocolConfig: seed("protocol_config"),
  experiment: seed("experiment"),
  vault: seed("vault"),
  vaultAuthority: seed("vault_authority"),
  cohortSet: seed("cohort_set"),
  epoch: seed("epoch"),
  evaluation: seed("evaluation"),
  distribution: seed("distribution"),
  claim: seed("claim"),
  challenge: seed("challenge"),
  bondVault: seed("bond_vault"),
  cpiAuthority: seed("cpi_authority"),
} as const;
