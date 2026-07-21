/**
 * Program-derived address (PDA) helpers. Seeds mirror the on-chain
 * `#[account(seeds = ...)]` declarations exactly.
 *
 * Endianness note (serialization.md §6.6): PDA seeds that carry an integer use
 * LITTLE-ENDIAN (`to_le_bytes()`, the Solana/Anchor address-derivation idiom).
 * This is INTENTIONALLY different from the BIG-ENDIAN encoding of the same
 * `leaf_index` inside a hashed reward-leaf preimage — neither may be changed to
 * match the other.
 */

import { PublicKey } from "@solana/web3.js";

import {
  CHALLENGE_PROGRAM_ID,
  EVIDENCE_REGISTRY_PROGRAM_ID,
  EXPERIMENT_REGISTRY_PROGRAM_ID,
  SEEDS,
  SETTLEMENT_PROGRAM_ID,
} from "./programs";
import { experimentIdHash } from "./crypto";

function u64le(n: bigint): Uint8Array {
  const b = new Uint8Array(8);
  new DataView(b.buffer).setBigUint64(0, n, true); // little-endian (PDA seed idiom)
  return b;
}

function findPda(seeds: Uint8Array[], programId: PublicKey): PublicKey {
  return PublicKey.findProgramAddressSync(
    seeds.map((s) => Buffer.from(s)),
    programId,
  )[0];
}

// -- experiment-registry PDAs --

export function protocolConfigPda(): PublicKey {
  return findPda([SEEDS.protocolConfig], EXPERIMENT_REGISTRY_PROGRAM_ID);
}

/** `experiment` PDA seeded by `experiment_id_hash = SHA-256("CRP-exp-id"||id)`. */
export function experimentPda(experimentId: string): PublicKey {
  return findPda(
    [SEEDS.experiment, experimentIdHash(experimentId)],
    EXPERIMENT_REGISTRY_PROGRAM_ID,
  );
}

export function experimentPdaFromHash(idHash: Uint8Array): PublicKey {
  return findPda([SEEDS.experiment, idHash], EXPERIMENT_REGISTRY_PROGRAM_ID);
}

export function vaultPda(experiment: PublicKey): PublicKey {
  return findPda([SEEDS.vault, experiment.toBytes()], EXPERIMENT_REGISTRY_PROGRAM_ID);
}

export function cohortSetPda(experiment: PublicKey): PublicKey {
  return findPda([SEEDS.cohortSet, experiment.toBytes()], EXPERIMENT_REGISTRY_PROGRAM_ID);
}

// -- evidence-registry PDAs --

export function epochPda(experiment: PublicKey, epochIndex: bigint): PublicKey {
  return findPda(
    [SEEDS.epoch, experiment.toBytes(), u64le(epochIndex)],
    EVIDENCE_REGISTRY_PROGRAM_ID,
  );
}

// -- settlement PDAs --

/** The vault_authority PDA lives under the SETTLEMENT program (it signs vault transfers). */
export function vaultAuthorityPda(experiment: PublicKey): PublicKey {
  return findPda([SEEDS.vaultAuthority, experiment.toBytes()], SETTLEMENT_PROGRAM_ID);
}

export function evaluationPda(experiment: PublicKey): PublicKey {
  return findPda([SEEDS.evaluation, experiment.toBytes()], SETTLEMENT_PROGRAM_ID);
}

export function distributionPda(experiment: PublicKey): PublicKey {
  return findPda([SEEDS.distribution, experiment.toBytes()], SETTLEMENT_PROGRAM_ID);
}

/** ClaimReceipt nullifier PDA. `leaf_index` is LITTLE-ENDIAN here (see file header). */
export function claimReceiptPda(experiment: PublicKey, leafIndex: bigint): PublicKey {
  return findPda(
    [SEEDS.claim, experiment.toBytes(), u64le(leafIndex)],
    SETTLEMENT_PROGRAM_ID,
  );
}

export function settlementCpiAuthorityPda(): PublicKey {
  return findPda([SEEDS.cpiAuthority], SETTLEMENT_PROGRAM_ID);
}

// -- challenge PDAs --

export function challengePda(experiment: PublicKey, challenger: PublicKey): PublicKey {
  return findPda(
    [SEEDS.challenge, experiment.toBytes(), challenger.toBytes()],
    CHALLENGE_PROGRAM_ID,
  );
}

export function bondVaultPda(challenge: PublicKey): PublicKey {
  return findPda([SEEDS.bondVault, challenge.toBytes()], CHALLENGE_PROGRAM_ID);
}

export function challengeCpiAuthorityPda(): PublicKey {
  return findPda([SEEDS.cpiAuthority], CHALLENGE_PROGRAM_ID);
}
