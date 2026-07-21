/**
 * `CausalRewardsClient` — the typed entry point to the four Causal Rewards Protocol
 * Solana programs. Thin, IDL-aligned wrappers: every instruction method resolves the
 * canonical PDAs (see `pda.ts`) and returns an Anchor `MethodsBuilder`, so callers
 * keep full control (`.rpc()`, `.instruction()`, `.transaction()`, `.signers()`).
 *
 * The client never hides a network call and never exposes an API that would let a
 * caller violate a protocol invariant (e.g. there is no "edit frozen manifest" path;
 * `freeze_experiment` only takes the manifest hash). Map raw RPC failures to readable
 * errors with `mapProgramError` (see `errors.ts`).
 */

import { AnchorProvider, BN, Program, type Idl } from "@coral-xyz/anchor";
import {
  Keypair,
  PublicKey,
  SystemProgram,
  SYSVAR_RENT_PUBKEY,
} from "@solana/web3.js";

import experimentRegistryIdl from "./idl/experiment_registry.json";
import evidenceRegistryIdl from "./idl/evidence_registry.json";
import settlementIdl from "./idl/settlement.json";
import challengeIdl from "./idl/challenge.json";

import { TOKEN_PROGRAM_ID } from "./programs";
import * as pda from "./pda";
import {
  ChallengeAccount,
  ClaimReceiptAccount,
  CohortSetAccount,
  DistributionAccount,
  EvaluationAccount,
  EvidenceEpochAccount,
  ExperimentAccount,
  ProtocolConfigAccount,
} from "./accounts";
import { experimentIdHash } from "./crypto";
import { buildRewardProof, RewardLeaf } from "./crypto/reward";
import { AssignmentDesign, buildAssignmentRoot } from "./crypto/assignment";

/** A `bigint | number | BN` we can coerce to Anchor's `BN` losslessly. */
export type Numeric = bigint | number | BN;

function toBN(x: Numeric): BN {
  if (x instanceof BN) return x;
  return new BN(x.toString());
}

/** Coerce 32-byte input (hex is NOT accepted here — pass raw bytes) to a plain array. */
function bytes32(b: Uint8Array | number[]): number[] {
  const arr = Array.from(b);
  if (arr.length !== 32) throw new Error(`expected 32 bytes, got ${arr.length}`);
  return arr;
}

/** Anchor's `MethodsBuilder` is not exported as a public type; this is the surface we use. */
export interface IxBuilder {
  rpc(opts?: unknown): Promise<string>;
  instruction(): Promise<import("@solana/web3.js").TransactionInstruction>;
  transaction(): Promise<import("@solana/web3.js").Transaction>;
  signers(signers: Keypair[]): IxBuilder;
  accountsPartial(accounts: Record<string, PublicKey>): IxBuilder;
}

/** Args for `create_experiment` (mirrors `CreateExperimentArgs` in the IDL). */
export interface CreateExperimentArgs {
  experimentId: string;
  evaluator: PublicKey;
  authorityThreshold: number;
  authoritySigners: PublicKey[];
  analysisContainerDigest: Uint8Array | number[];
  rewardCurveHash: Uint8Array | number[];
  seedCommitment: Uint8Array | number[];
  budgetBaseUnits: Numeric;
  challengeBondBaseUnits: Numeric;
  freezeBy: Numeric;
  activeStart: Numeric;
  activeEnd: Numeric;
  evaluationDeadline: Numeric;
  challengeWindowSeconds: Numeric;
  claimWindowSeconds: Numeric;
}

/** Args for `post_evidence_epoch` (mirrors `EvidenceEpochArgs`). */
export interface EvidenceEpochArgs {
  cohortId: string;
  timeStart: Numeric;
  timeEnd: Numeric;
  signerSetRoot: Uint8Array | number[];
  observationsRoot: Uint8Array | number[];
  acceptedCount: Numeric;
  rejectedCount: Numeric;
  distinctSigners: Numeric;
  contentHash: Uint8Array | number[];
  producer: PublicKey;
}

export class CausalRewardsClient {
  readonly registry: Program;
  readonly evidence: Program;
  readonly settlement: Program;
  readonly challenge: Program;

  constructor(readonly provider: AnchorProvider) {
    this.registry = new Program(experimentRegistryIdl as Idl, provider);
    this.evidence = new Program(evidenceRegistryIdl as Idl, provider);
    this.settlement = new Program(settlementIdl as Idl, provider);
    this.challenge = new Program(challengeIdl as Idl, provider);
  }

  // Internal: untyped methods namespace (public method signatures below are typed).
  private m(p: Program): Record<string, (...args: unknown[]) => IxBuilder> {
    return (p as unknown as { methods: Record<string, (...a: unknown[]) => IxBuilder> })
      .methods;
  }

  // ── experiment-registry ──────────────────────────────────────────────────

  /** Initialize the singleton `ProtocolConfig` (devnet-only, fees hard-zero). */
  initProtocolConfig(args: {
    schemaVersion: number;
    evidenceProgram: PublicKey;
    settlementProgram: PublicKey;
    challengeProgram: PublicKey;
    abortGraceSeconds: Numeric;
    admin: PublicKey;
  }): IxBuilder {
    return this.m(this.registry)
      .initProtocolConfig(
        args.schemaVersion,
        args.evidenceProgram,
        args.settlementProgram,
        args.challengeProgram,
        toBN(args.abortGraceSeconds),
      )
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        admin: args.admin,
        systemProgram: SystemProgram.programId,
      });
  }

  /** Create a new experiment (Draft). Funds the vault from `coordinatorFunding`. */
  createExperiment(args: {
    create: CreateExperimentArgs;
    mint: PublicKey;
    coordinator: PublicKey;
    coordinatorFunding: PublicKey;
  }): IxBuilder {
    const idHash = experimentIdHash(args.create.experimentId);
    const experiment = pda.experimentPdaFromHash(idHash);
    const idlArgs = {
      experimentId: args.create.experimentId,
      evaluator: args.create.evaluator,
      authorityThreshold: args.create.authorityThreshold,
      authoritySigners: args.create.authoritySigners,
      analysisContainerDigest: bytes32(args.create.analysisContainerDigest),
      rewardCurveHash: bytes32(args.create.rewardCurveHash),
      seedCommitment: bytes32(args.create.seedCommitment),
      budgetBaseUnits: toBN(args.create.budgetBaseUnits),
      challengeBondBaseUnits: toBN(args.create.challengeBondBaseUnits),
      freezeBy: toBN(args.create.freezeBy),
      activeStart: toBN(args.create.activeStart),
      activeEnd: toBN(args.create.activeEnd),
      evaluationDeadline: toBN(args.create.evaluationDeadline),
      challengeWindowSeconds: toBN(args.create.challengeWindowSeconds),
      claimWindowSeconds: toBN(args.create.claimWindowSeconds),
    };
    return this.m(this.registry)
      .createExperiment(Array.from(idHash), idlArgs)
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        vault: pda.vaultPda(experiment),
        vaultAuthority: pda.vaultAuthorityPda(experiment),
        mint: args.mint,
        coordinatorFunding: args.coordinatorFunding,
        coordinator: args.coordinator,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        rent: SYSVAR_RENT_PUBKEY,
      });
  }

  /** Freeze the manifest (Draft → Frozen). Only the 32-byte manifest hash is taken. */
  freezeExperiment(experimentId: string, manifestHash: Uint8Array | number[]): IxBuilder {
    const experiment = pda.experimentPda(experimentId);
    return this.m(this.registry)
      .freezeExperiment(bytes32(manifestHash))
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
      });
  }

  /** Publish the committed assignment (cohort) Merkle root. */
  publishCohortRoot(args: {
    experimentId: string;
    cohortRoot: Uint8Array | number[];
    cohortCount: number;
    coordinator: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    return this.m(this.registry)
      .publishCohortRoot(bytes32(args.cohortRoot), args.cohortCount)
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        cohortSet: pda.cohortSetPda(experiment),
        coordinator: args.coordinator,
        systemProgram: SystemProgram.programId,
      });
  }

  /** Reveal the assignment seed (must open the frozen commitment; freeze-before-reveal). */
  revealSeed(experimentId: string, seed: Uint8Array | number[], coordinator: PublicKey): IxBuilder {
    const experiment = pda.experimentPda(experimentId);
    return this.m(this.registry)
      .revealSeed(bytes32(seed))
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        coordinator,
      });
  }

  /** `mark_aborted` — registry-side status transition, CPI-authorized from settlement. */
  markAborted(experimentId: string, callerAuthority: PublicKey): IxBuilder {
    return this.m(this.registry)
      .markAborted()
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment: pda.experimentPda(experimentId),
        callerAuthority,
      });
  }

  // ── evidence-registry ────────────────────────────────────────────────────

  /** Anchor an evidence epoch. `prevEpoch` must be the previous epoch PDA (or epoch 0's own PDA at index 0 — pass what the program expects). */
  postEvidenceEpoch(args: {
    experimentId: string;
    epochIndex: Numeric;
    args: EvidenceEpochArgs;
    coordinator: PublicKey;
    prevEpoch: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    const epochIndex = toBN(args.epochIndex);
    const idlArgs = {
      cohortId: args.args.cohortId,
      timeStart: toBN(args.args.timeStart),
      timeEnd: toBN(args.args.timeEnd),
      signerSetRoot: bytes32(args.args.signerSetRoot),
      observationsRoot: bytes32(args.args.observationsRoot),
      acceptedCount: toBN(args.args.acceptedCount),
      rejectedCount: toBN(args.args.rejectedCount),
      distinctSigners: toBN(args.args.distinctSigners),
      contentHash: bytes32(args.args.contentHash),
      producer: args.args.producer,
    };
    return this.m(this.evidence)
      .postEvidenceEpoch(epochIndex, idlArgs)
      .accountsPartial({
        experiment,
        evidenceEpoch: pda.epochPda(experiment, BigInt(epochIndex.toString())),
        prevEpoch: args.prevEpoch,
        coordinator: args.coordinator,
        systemProgram: SystemProgram.programId,
      });
  }

  // ── settlement ───────────────────────────────────────────────────────────

  /** Submit the evaluation result (result-artifact hash, reward root, container digest). */
  submitEvaluation(args: {
    experimentId: string;
    resultArtifactHash: Uint8Array | number[];
    rewardRoot: Uint8Array | number[];
    analysisContainerDigest: Uint8Array | number[];
    evaluator: PublicKey;
    epochZero: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    return this.m(this.settlement)
      .submitEvaluation(
        bytes32(args.resultArtifactHash),
        bytes32(args.rewardRoot),
        bytes32(args.analysisContainerDigest),
      )
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        evaluation: pda.evaluationPda(experiment),
        epochZero: args.epochZero,
        cpiAuthority: pda.settlementCpiAuthorityPda(),
        evaluator: args.evaluator,
        experimentRegistryProgram: this.registry.programId,
        systemProgram: SystemProgram.programId,
      });
  }

  /** Finalize the distribution: lock the reward root and total allocation (Evaluating → Final path). */
  finalizeDistribution(args: {
    experimentId: string;
    totalAllocatedBaseUnits: Numeric;
    finalizer: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    return this.m(this.settlement)
      .finalizeDistribution(toBN(args.totalAllocatedBaseUnits))
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        evaluation: pda.evaluationPda(experiment),
        distribution: pda.distributionPda(experiment),
        cpiAuthority: pda.settlementCpiAuthorityPda(),
        finalizer: args.finalizer,
        experimentRegistryProgram: this.registry.programId,
        systemProgram: SystemProgram.programId,
      });
  }

  /**
   * Claim a reward leaf against the finalized reward root. Prefer `buildClaim`, which
   * constructs the Merkle proof for you from the full leaf set.
   */
  claimReward(args: {
    experimentId: string;
    leafIndex: Numeric;
    amountBaseUnits: Numeric;
    proof: Array<{ sibling: Uint8Array | number[]; siblingIsLeft: boolean }>;
    recipient: PublicKey;
    recipientToken: PublicKey;
    vault: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    const leafIndex = toBN(args.leafIndex);
    const idlProof = args.proof.map((s) => ({
      sibling: bytes32(s.sibling),
      siblingIsLeft: s.siblingIsLeft,
    }));
    return this.m(this.settlement)
      .claimReward(leafIndex, toBN(args.amountBaseUnits), idlProof)
      .accountsPartial({
        experiment,
        distribution: pda.distributionPda(experiment),
        claimReceipt: pda.claimReceiptPda(experiment, BigInt(leafIndex.toString())),
        vault: args.vault,
        vaultAuthority: pda.vaultAuthorityPda(experiment),
        recipientToken: args.recipientToken,
        recipient: args.recipient,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
      });
  }

  /**
   * Convenience: build the Merkle proof for `leafIndex` from the full reward-leaf set
   * (matching the §6.6 verifier and the settlement program byte-for-byte) and return a
   * ready `claim_reward` builder. Throws if the leaf's implied root disagrees with
   * `expectedRoot` (pass the on-chain `Distribution.rewardRoot` to guard against a
   * stale/incorrect leaf set before you spend a transaction).
   */
  buildClaim(args: {
    experimentId: string;
    leaves: RewardLeaf[];
    leafIndex: Numeric;
    recipientToken: PublicKey;
    vault: PublicKey;
    expectedRoot?: Uint8Array | number[];
  }): { builder: IxBuilder; leaf: RewardLeaf; root: Uint8Array } {
    const leafIndex = BigInt(toBN(args.leafIndex).toString());
    const { leaf, proof, root } = buildRewardProof(args.leaves, leafIndex);
    if (args.expectedRoot !== undefined) {
      const expected = bytes32(args.expectedRoot);
      for (let i = 0; i < 32; i++) {
        if (root[i] !== expected[i]) {
          throw new Error(
            "reward leaf set does not reproduce the expected (on-chain) reward_root; " +
              "refusing to build a claim that would fail InvalidMerkleProof on-chain",
          );
        }
      }
    }
    const builder = this.claimReward({
      experimentId: args.experimentId,
      leafIndex: leaf.leafIndex,
      amountBaseUnits: leaf.amountBaseUnits,
      proof: proof.map((s) => ({ sibling: s.sibling, siblingIsLeft: s.siblingIsLeft })),
      recipient: leaf.recipient,
      recipientToken: args.recipientToken,
      vault: args.vault,
    });
    return { builder, leaf, root };
  }

  /** Recover unclaimed budget after the claim window (Final → Closed). */
  closeExperiment(args: {
    experimentId: string;
    vault: PublicKey;
    recoveryToken: PublicKey;
    cranker: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    return this.m(this.settlement)
      .closeExperiment()
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        distribution: pda.distributionPda(experiment),
        vault: args.vault,
        vaultAuthority: pda.vaultAuthorityPda(experiment),
        recoveryToken: args.recoveryToken,
        cpiAuthority: pda.settlementCpiAuthorityPda(),
        cranker: args.cranker,
        experimentRegistryProgram: this.registry.programId,
        tokenProgram: TOKEN_PROGRAM_ID,
      });
  }

  /** Abort a pre-Final experiment and recover the full vault (settlement-side). */
  abortExperiment(args: {
    experimentId: string;
    vault: PublicKey;
    recoveryToken: PublicKey;
    cranker: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    return this.m(this.settlement)
      .abortExperiment()
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        distribution: pda.distributionPda(experiment),
        vault: args.vault,
        vaultAuthority: pda.vaultAuthorityPda(experiment),
        recoveryToken: args.recoveryToken,
        cpiAuthority: pda.settlementCpiAuthorityPda(),
        cranker: args.cranker,
        experimentRegistryProgram: this.registry.programId,
        tokenProgram: TOKEN_PROGRAM_ID,
      });
  }

  // ── challenge ────────────────────────────────────────────────────────────

  /** Open a bonded challenge against a live evaluation (Evaluating → Challenged). */
  openChallenge(args: {
    experimentId: string;
    reasonCode: number;
    bondAmount: Numeric;
    mint: PublicKey;
    challengerToken: PublicKey;
    challenger: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    const challenge = pda.challengePda(experiment, args.challenger);
    return this.m(this.challenge)
      .openChallenge(args.reasonCode, toBN(args.bondAmount))
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        challenge,
        bondVault: pda.bondVaultPda(challenge),
        mint: args.mint,
        challengerToken: args.challengerToken,
        cpiAuthority: pda.challengeCpiAuthorityPda(),
        challenger: args.challenger,
        experimentRegistryProgram: this.registry.programId,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        rent: SYSVAR_RENT_PUBKEY,
      });
  }

  /** Resolve a challenge (upheld/dismissed); routes the bond and transitions status. */
  resolveChallenge(args: {
    experimentId: string;
    challenger: PublicKey;
    upheld: boolean;
    bondVault: PublicKey;
    bondDestination: PublicKey;
    resolver: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    const challenge = pda.challengePda(experiment, args.challenger);
    return this.m(this.challenge)
      .resolveChallenge(args.upheld)
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        challenge,
        bondVault: args.bondVault,
        bondDestination: args.bondDestination,
        cpiAuthority: pda.challengeCpiAuthorityPda(),
        resolver: args.resolver,
        experimentRegistryProgram: this.registry.programId,
        tokenProgram: TOKEN_PROGRAM_ID,
      });
  }

  /** Refund a challenger's bond after the experiment was aborted (challenge-side). */
  refundBond(args: {
    experimentId: string;
    challenger: PublicKey;
    bondVault: PublicKey;
    bondDestination: PublicKey;
    cranker: PublicKey;
  }): IxBuilder {
    const experiment = pda.experimentPda(args.experimentId);
    const challenge = pda.challengePda(experiment, args.challenger);
    return this.m(this.challenge)
      .refundBond()
      .accountsPartial({
        protocolConfig: pda.protocolConfigPda(),
        experiment,
        challenge,
        bondVault: args.bondVault,
        bondDestination: args.bondDestination,
        cranker: args.cranker,
        experimentRegistryProgram: this.registry.programId,
        tokenProgram: TOKEN_PROGRAM_ID,
      });
  }

  // ── account fetchers ─────────────────────────────────────────────────────

  private acct(p: Program): Record<string, { fetch(addr: PublicKey): Promise<unknown> }> {
    return (p as unknown as {
      account: Record<string, { fetch(addr: PublicKey): Promise<unknown> }>;
    }).account;
  }

  async fetchProtocolConfig(): Promise<ProtocolConfigAccount> {
    return (await this.acct(this.registry).protocolConfig.fetch(
      pda.protocolConfigPda(),
    )) as ProtocolConfigAccount;
  }

  async fetchExperiment(experimentId: string): Promise<ExperimentAccount> {
    return (await this.acct(this.registry).experiment.fetch(
      pda.experimentPda(experimentId),
    )) as ExperimentAccount;
  }

  async fetchExperimentAt(address: PublicKey): Promise<ExperimentAccount> {
    return (await this.acct(this.registry).experiment.fetch(address)) as ExperimentAccount;
  }

  async fetchCohortSet(experimentId: string): Promise<CohortSetAccount> {
    return (await this.acct(this.registry).cohortSet.fetch(
      pda.cohortSetPda(pda.experimentPda(experimentId)),
    )) as CohortSetAccount;
  }

  async fetchEvidenceEpoch(experimentId: string, epochIndex: Numeric): Promise<EvidenceEpochAccount> {
    const experiment = pda.experimentPda(experimentId);
    return (await this.acct(this.evidence).evidenceEpoch.fetch(
      pda.epochPda(experiment, BigInt(toBN(epochIndex).toString())),
    )) as EvidenceEpochAccount;
  }

  async fetchEvaluation(experimentId: string): Promise<EvaluationAccount> {
    return (await this.acct(this.settlement).evaluation.fetch(
      pda.evaluationPda(pda.experimentPda(experimentId)),
    )) as EvaluationAccount;
  }

  async fetchDistribution(experimentId: string): Promise<DistributionAccount> {
    return (await this.acct(this.settlement).distribution.fetch(
      pda.distributionPda(pda.experimentPda(experimentId)),
    )) as DistributionAccount;
  }

  async fetchClaimReceipt(experimentId: string, leafIndex: Numeric): Promise<ClaimReceiptAccount> {
    const experiment = pda.experimentPda(experimentId);
    return (await this.acct(this.settlement).claimReceipt.fetch(
      pda.claimReceiptPda(experiment, BigInt(toBN(leafIndex).toString())),
    )) as ClaimReceiptAccount;
  }

  async fetchChallenge(experimentId: string, challenger: PublicKey): Promise<ChallengeAccount> {
    return (await this.acct(this.challenge).challenge.fetch(
      pda.challengePda(pda.experimentPda(experimentId), challenger),
    )) as ChallengeAccount;
  }

  // ── determinism-safe builders (re-exported for discoverability) ───────────

  /**
   * Build the assignment (cohort) Merkle root from a revealed seed + cohort list +
   * design — byte-identical to the verifier reference and `crp-crypto`. Feed the
   * resulting root to `publishCohortRoot`.
   */
  buildAssignmentRoot(
    seed: Uint8Array,
    experimentId: string,
    cohortIds: string[],
    design: AssignmentDesign,
  ): ReturnType<typeof buildAssignmentRoot> {
    return buildAssignmentRoot(seed, experimentId, cohortIds, design);
  }
}
