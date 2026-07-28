/**
 * The read surface. Every view in the dashboard consumes an `ExperimentSnapshot` and nothing
 * else, so the same components render an offline audit bundle and live devnet accounts.
 *
 * AVAILABILITY INVARIANT: this interface is a convenience layer. Every snapshot carries the
 * public locations (`bundleUrl`, `verifyCommand`) that let a third party reproduce the same
 * facts with `crp-verify` and zero dependence on this dashboard being up.
 */
import type {
  AssignmentRow,
  BundleFiles,
  ChallengeView,
  DistributionView,
  EvidenceEpochView,
  ExperimentView,
  ProvenanceRecord,
  PublishedRoots,
  ResultView,
} from "../types";

export type SourceKind = "bundle" | "rpc" | "composite";

export interface NetworkLabel {
  /** Always "devnet" in the MVP (invariant 7). Rendered prominently; no mainnet affordances. */
  cluster: string;
  endpoint: string | null;
}

export interface ExperimentSummary {
  experimentId: string;
  title: string;
  status: ExperimentView["status"];
  manifestHashHex: string;
}

/** On-chain anchors, for `crp-verify --onchain`. Exported alongside the bundle. */
export interface OnchainCommitments {
  manifest_hash?: string;
  cohort_root?: string;
  assignment_root?: string;
  reward_root?: string;
  result_artifact_hash?: string;
}

export interface ExperimentSnapshot {
  source: { id: string; kind: SourceKind; network: NetworkLabel };
  experiment: ExperimentView;
  roots: PublishedRoots | null;
  provenance: ProvenanceRecord | null;
  assignment: AssignmentRow[];
  evidence: EvidenceEpochView[];
  result: ResultView;
  challenges: ChallengeView[];
  distribution: DistributionView;
  /** Raw bundle bytes when this source has them. Null = export unavailable from here. */
  bundleFiles: BundleFiles | null;
  /** Public, content-addressed location of the bundle. The dashboard is never the origin. */
  bundleUrl: string | null;
  onchainCommitments: OnchainCommitments | null;
  /** Things this source could not read. Shown to the viewer, never swallowed. */
  warnings: string[];
}

export interface ProtocolDataSource {
  readonly id: string;
  readonly kind: SourceKind;
  readonly network: NetworkLabel;
  listExperiments(): Promise<ExperimentSummary[]>;
  loadExperiment(experimentId: string): Promise<ExperimentSnapshot>;
}
