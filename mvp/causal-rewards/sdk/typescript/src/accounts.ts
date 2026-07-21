/**
 * Decoded on-chain account shapes for the four M2 programs.
 *
 * These mirror the IDL account structs exactly (do not add or reinterpret fields —
 * conform to the IDL). Integer fields that are `u64`/`i64` on-chain are surfaced as
 * `BN` (as Anchor decodes them); 32-byte hash/seed fields are surfaced as `number[]`
 * (Anchor's `array<u8;32>` decoding). Use `bytesToHex` to render a hash field.
 */

import { BN } from "@coral-xyz/anchor";
import { PublicKey } from "@solana/web3.js";

/** Experiment lifecycle status (experiment_registry `ExperimentStatus`). */
export type ExperimentStatus =
  | { draft: Record<string, never> }
  | { frozen: Record<string, never> }
  | { active: Record<string, never> }
  | { evaluating: Record<string, never> }
  | { challenged: Record<string, never> }
  | { final: Record<string, never> }
  | { closed: Record<string, never> };

/** `ProtocolConfig` PDA — global protocol parameters and registered program authorities. */
export interface ProtocolConfigAccount {
  admin: PublicKey;
  feeBps: number;
  paused: boolean;
  cluster: number;
  schemaVersion: number;
  evidenceProgram: PublicKey;
  settlementProgram: PublicKey;
  challengeProgram: PublicKey;
  abortGraceSeconds: BN;
  bump: number;
}

/** `Experiment` PDA — the per-experiment root record (frozen manifest hash, windows, status). */
export interface ExperimentAccount {
  status: ExperimentStatus;
  coordinator: PublicKey;
  evaluator: PublicKey;
  authorityThreshold: number;
  authoritySigners: PublicKey[];
  experimentId: string;
  manifestHash: number[];
  analysisContainerDigest: number[];
  rewardCurveHash: number[];
  seedCommitment: number[];
  mint: PublicKey;
  vault: PublicKey;
  budgetBaseUnits: BN;
  challengeBondBaseUnits: BN;
  freezeBy: BN;
  activeStart: BN;
  activeEnd: BN;
  evaluationDeadline: BN;
  challengeWindowSeconds: BN;
  claimWindowSeconds: BN;
  cohortPublished: boolean;
  revealedSeed: number[] | null;
  evaluationValid: boolean;
  openChallenges: number;
  challengeWindowEnd: BN;
  claimWindowEnd: BN;
  aborted: boolean;
  createdAt: BN;
  bump: number;
  vaultBump: number;
}

/** `CohortSet` PDA — the published assignment (cohort) Merkle root. */
export interface CohortSetAccount {
  experiment: PublicKey;
  cohortRoot: number[];
  cohortCount: number;
  bump: number;
}

/** `EvidenceEpoch` PDA — one anchored evidence epoch (batch roots + summary counts). */
export interface EvidenceEpochAccount {
  experiment: PublicKey;
  epochIndex: BN;
  cohortId: string;
  timeStart: BN;
  timeEnd: BN;
  signerSetRoot: number[];
  observationsRoot: number[];
  acceptedCount: BN;
  rejectedCount: BN;
  distinctSigners: BN;
  contentHash: number[];
  producer: PublicKey;
  bump: number;
}

/** `Evaluation` PDA — the submitted result-artifact hash + reward root + container digest. */
export interface EvaluationAccount {
  experiment: PublicKey;
  resultArtifactHash: number[];
  rewardRoot: number[];
  analysisContainerDigest: number[];
  evaluator: PublicKey;
  bump: number;
}

/** `Distribution` PDA — the finalized reward root and budget accounting for claims. */
export interface DistributionAccount {
  experiment: PublicKey;
  rewardRoot: number[];
  totalAllocatedBaseUnits: BN;
  unallocatedBaseUnits: BN;
  claimWindowEnd: BN;
  bump: number;
}

/** `ClaimReceipt` PDA — single-use nullifier proving a reward leaf was claimed. */
export interface ClaimReceiptAccount {
  experiment: PublicKey;
  leafIndex: BN;
  recipient: PublicKey;
  amountBaseUnits: BN;
  bump: number;
}

/** `Challenge` PDA — a bonded challenge record and its resolution state. */
export interface ChallengeAccount {
  experiment: PublicKey;
  challenger: PublicKey;
  bondAmount: BN;
  reasonCode: number;
  resolution: number;
  bondVault: PublicKey;
  bump: number;
}

/** Render a decoded 32-byte hash field (`number[]`) as lowercase hex. */
export function bytesToHex(bytes: number[] | Uint8Array): string {
  let s = "";
  for (const b of bytes) s += (b & 0xff).toString(16).padStart(2, "0");
  return s;
}
