/**
 * The dashboard's view model.
 *
 * Every field here maps 1:1 onto something the protocol actually commits — an on-chain
 * account field (see `@causal-rewards/sdk` `accounts.ts`) or a slot in the ratified audit
 * bundle (see `specs/` and `docs/m3-integration-and-spec-round.md` §1). Nothing is derived
 * causal science; the dashboard displays committed numbers and says where each came from.
 *
 * INVARIANT 5 (data minimization): no field in this model may carry raw telemetry, exact
 * coordinates, or personal data. Cohort identifiers, hashes, roots, counts and claim state
 * only. `src/protocol/privacy.ts` enforces the same rule on anything we export.
 */

/** Where a displayed value came from. The UI always shows this — provenance is the product. */
export type Provenance =
  | "onchain" // read from a Solana account via the TypeScript SDK
  | "bundle" // read from the content-addressed audit bundle
  | "derived"; // arithmetic on displayed committed values (always labelled in the UI)

/** `ExperimentStatus` on-chain, flattened to a string (SDK surfaces it as an enum object). */
export type ExperimentStatus =
  | "draft"
  | "frozen"
  | "active"
  | "evaluating"
  | "challenged"
  | "final"
  | "closed";

export interface ManifestWindows {
  freezeBy: string;
  activeStart: string;
  activeEnd: string;
  evaluationDeadline: string;
  challengeWindowSeconds: string;
  claimWindowSeconds: string;
}

export interface Authorities {
  coordinatorPubkey: string;
  evaluatorPubkey: string;
  multisigThreshold: string;
  multisigSigners: string[];
  challengeBondBaseUnits: string;
}

/** The frozen manifest, parsed. Kept close to the on-disk JSON: `specs/manifest.schema.json`. */
export interface FrozenManifest {
  experimentId: string;
  title: string;
  description: string;
  specVersion: string;
  manifestVersion: string;
  cluster: string;
  createdAt: string;
  windows: ManifestWindows;
  authorities: Authorities;
  primaryOutcome: {
    metricId: string;
    description: string;
    unitOfMeasure: string;
    improvementDirection: "increase" | "decrease" | string;
  };
  estimand: {
    unitType: string;
    effectDefinition: string;
    cohortCount: string;
    cohortScheme: string;
    spatialResolution: string;
    blockCount: string;
    blockSeconds: string;
  };
  design: {
    template: string;
    eligibleForStrongCausalClaim: boolean;
    parameters: Record<string, string>;
  };
  treatment: {
    assignmentMethod: string;
    treatedFractionMicro: string;
    description: string;
  };
  analysisPlan: {
    estimator: string;
    standardErrorMethod: string;
    testSidedness: string;
    confidenceLevelMicro: string;
    criticalValueMicro: string;
    criticalValueReference: string;
    covariateAdjustment: string[];
    sensitivityAnalyses: string[];
    minimumSample: Record<string, string>;
    analysisContainerDigest: string;
  };
  rewardPolicy: RewardPolicyRaw;
  seedCommitment: { algo: string; scheme: string; commitmentHex: string };
  /** Anything present in the manifest that this version of the UI does not model. */
  unmodeled: Record<string, unknown>;
}

/**
 * The reward-policy block exactly as frozen. Deliberately *raw*: the dashboard never
 * hardcodes curve parameters or a multiplicity regime. `rewardPolicy.ts` is the only place
 * that interprets this, so the pending v1.2 policy decision cannot force a UI rewrite.
 */
export interface RewardPolicyRaw {
  budgetBaseUnits: string;
  mint: string;
  overflowPolicy: string;
  unusedBudgetPolicy: string;
  rewardCurveType: string;
  rewardCurveBreakpoints: Array<[string, string]>;
  rewardCurveHash: string;
  intraCohortSplit: Record<string, string>;
  positiveImprovementTransform: Record<string, string>;
  /** Every other key under `reward_policy`, untouched. Rendered generically. */
  extra: Record<string, unknown>;
}

export interface ExperimentView {
  experimentId: string;
  status: ExperimentStatus;
  statusProvenance: Provenance;
  manifestHashHex: string;
  manifest: FrozenManifest | null;
  /** Present only once the seed has been revealed on-chain. Absent = still sealed. */
  revealedSeedHex: string | null;
  cohortPublished: boolean;
  cohortRootHex: string | null;
  cohortCount: number | null;
  evaluationValid: boolean | null;
  openChallenges: number | null;
  aborted: boolean | null;
  challengeWindowEnd: string | null;
  claimWindowEnd: string | null;
  cluster: string;
}

export interface EvidenceEpochView {
  epochIndex: number;
  rootHex: string;
  /** Bundle-side: the parquet file that reproduces this root. */
  file: string | null;
  leafCount: number | null;
  /** On-chain-side fields; null when reading from a bundle only. */
  cohortId: string | null;
  timeStart: string | null;
  timeEnd: string | null;
  signerSetRootHex: string | null;
  observationsRootHex: string | null;
  acceptedCount: string | null;
  rejectedCount: string | null;
  distinctSigners: string | null;
  contentHashHex: string | null;
  producer: string | null;
}

export interface PrimaryEffect {
  pointEstimateMicro: string;
  standardErrorMicro: string;
  conservativeEffectMicro: string;
}

export interface CohortResultRow {
  cohortId: string;
  arm: string | null;
  pointEstimateMicro: string | null;
  standardErrorMicro: string | null;
  conservativeEffectMicro: string | null;
  eligible: boolean | null;
  /** Why a cohort contributed nothing. Rendered as a first-class outcome, never an error. */
  exclusionReason: string | null;
  observations: string | null;
}

export interface SensitivityRow {
  name: string;
  /** Free-form committed summary; rendered verbatim. */
  detail: string;
}

export interface ResultView {
  present: boolean;
  estimand: string | null;
  specVersion: string | null;
  engineName: string | null;
  analysisContainerDigest: string | null;
  resultArtifactHashHex: string | null;
  primaryEffect: PrimaryEffect | null;
  evidenceEpochRoots: string[];
  rewardSummary: { rewardRootHex: string | null; totalBaseUnits: string | null } | null;
  cohorts: CohortResultRow[];
  excluded: CohortResultRow[];
  sensitivity: SensitivityRow[];
  /** Anything else committed in analysis.json, shown raw so nothing is hidden. */
  raw: Record<string, unknown> | null;
}

export type ChallengeResolution = "unset" | "upheld" | "dismissed" | "refunded" | "unknown";

export interface ChallengeView {
  challenger: string;
  bondAmountBaseUnits: string;
  reasonCode: number;
  resolution: ChallengeResolution;
  resolutionRaw: number;
  bondVault: string | null;
}

export interface RewardLeafView {
  leafIndex: string;
  recipientHex: string;
  amountBaseUnits: string;
  leafHashHex: string;
  /** Only known from chain (a `ClaimReceipt` exists). Null = unknown from this source. */
  claimed: boolean | null;
}

export interface DistributionView {
  present: boolean;
  rewardRootHex: string | null;
  totalAllocatedBaseUnits: string | null;
  unallocatedBaseUnits: string | null;
  claimWindowEnd: string | null;
  leaves: RewardLeafView[];
  /** Total across leaves, from the bundle's committed leaf set. */
  leafTotalBaseUnits: string | null;
}

/** Roots as published in `roots.json`. Untrusted claims — the verifier reproduces them. */
export interface PublishedRoots {
  bundleLayoutVersion: string;
  manifestHashHex: string;
  assignmentRootHex: string | null;
  rewardRootHex: string | null;
  resultArtifactHashHex: string | null;
  evidenceEpochs: Array<{ epochIndex: number; rootHex: string; file: string }>;
}

export interface ProvenanceRecord {
  sourceCommit: string | null;
  containerDigest: string | null;
  executionTimestamp: string | null;
  manifestHashHex: string | null;
  note: string | null;
}

export interface AssignmentRow {
  cohortId: string;
  arm: string;
  leafHashHex: string;
}

/** Raw bundle bytes, keyed by POSIX-relative path. This is what the export writes. */
export type BundleFiles = ReadonlyMap<string, Uint8Array>;
