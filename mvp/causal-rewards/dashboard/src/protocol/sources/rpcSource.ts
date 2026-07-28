/**
 * Live devnet reads, through `@causal-rewards/sdk`.
 *
 * The SDK is the only path to on-chain state here — no hand-rolled account layouts, no second
 * data model (see the SDK's `accounts.ts`, which mirrors the IDL exactly). The SDK is loaded
 * with a dynamic import so the bundle-only path stays free of the wallet/RPC dependency tree.
 *
 * INVARIANT 7: devnet only. The endpoint is labelled on screen and there is no network
 * switcher, no wallet connect, and no transaction path anywhere in this dashboard — it reads.
 *
 * Off-chain artifacts (manifest body, analysis, reward leaves) are NOT on-chain. When a
 * bundle source is supplied, this source composes the two and shows which side each fact came
 * from; when it is not, the chain-only facts render and the rest is reported as unavailable.
 */
import { parseAnalysis } from "../bundle";
import { statusFromAnchor } from "../stateMachine";
import type { ChallengeResolution, ChallengeView, EvidenceEpochView } from "../types";
import type {
  ExperimentSnapshot,
  ExperimentSummary,
  NetworkLabel,
  OnchainCommitments,
  ProtocolDataSource,
} from "./types";

export const DEVNET_ENDPOINT = "https://api.devnet.solana.com";

export interface RpcSourceOptions {
  endpoint?: string;
  /** Experiment ids to show. The programs expose no on-chain registry index. */
  experimentIds: string[];
  /** Optional companion source for the off-chain, content-addressed artifacts. */
  bundleSource?: ProtocolDataSource | null;
  /** Public location of the bundle for an experiment id, for the "verify it yourself" link. */
  bundleUrlFor?: (experimentId: string) => string | null;
  maxEvidenceEpochs?: number;
}

function hex(bytes: number[] | Uint8Array | null | undefined): string {
  if (!bytes) return "";
  let s = "";
  for (const b of bytes) s += (b & 0xff).toString(16).padStart(2, "0");
  return s;
}
function isZero(h: string): boolean {
  return h.length === 0 || /^0+$/.test(h);
}
function big(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  const o = v as { toString(): string };
  return typeof o.toString === "function" ? o.toString() : null;
}

const RESOLUTIONS: Record<number, ChallengeResolution> = {
  0: "unset",
  1: "upheld",
  2: "dismissed",
  3: "refunded",
};

export class RpcDataSource implements ProtocolDataSource {
  readonly id = "solana-devnet";
  readonly kind = "composite" as const;
  readonly network: NetworkLabel;

  private readonly opts: RpcSourceOptions;
  private clientPromise: Promise<unknown> | null = null;

  constructor(opts: RpcSourceOptions) {
    this.opts = opts;
    this.network = { cluster: "devnet", endpoint: opts.endpoint ?? DEVNET_ENDPOINT };
  }

  /** Build a read-only Anchor provider. No wallet, no signer, no send path. */
  private async client(): Promise<any> {
    if (!this.clientPromise) {
      this.clientPromise = (async () => {
        const [{ CausalRewardsClient }, anchor, web3] = await Promise.all([
          import("@causal-rewards/sdk"),
          import("@coral-xyz/anchor"),
          import("@solana/web3.js"),
        ]);
        const connection = new web3.Connection(this.network.endpoint!, "confirmed");
        const readOnlyWallet = {
          publicKey: web3.PublicKey.default,
          signTransaction: () => Promise.reject(new Error("read-only dashboard: no signing")),
          signAllTransactions: () => Promise.reject(new Error("read-only dashboard: no signing")),
        };
        const provider = new anchor.AnchorProvider(connection, readOnlyWallet as never, {
          commitment: "confirmed",
        });
        return new CausalRewardsClient(provider);
      })();
    }
    return this.clientPromise;
  }

  async listExperiments(): Promise<ExperimentSummary[]> {
    const client = await this.client();
    const out: ExperimentSummary[] = [];
    for (const id of this.opts.experimentIds) {
      try {
        const e = await client.fetchExperiment(id);
        out.push({
          experimentId: id,
          title: id,
          status: statusFromAnchor(e.status),
          manifestHashHex: hex(e.manifestHash),
        });
      } catch {
        // An id that is not on this cluster is simply not listed. No invented rows.
      }
    }
    return out;
  }

  async loadExperiment(experimentId: string): Promise<ExperimentSnapshot> {
    const client = await this.client();
    const warnings: string[] = [];

    const e = await client.fetchExperiment(experimentId);
    const status = statusFromAnchor(e.status);

    let cohortRootHex: string | null = null;
    let cohortCount: number | null = null;
    if (e.cohortPublished) {
      try {
        const cs = await client.fetchCohortSet(experimentId);
        cohortRootHex = hex(cs.cohortRoot);
        cohortCount = Number(cs.cohortCount);
      } catch {
        warnings.push("CohortSet account not readable.");
      }
    }

    const evidence: EvidenceEpochView[] = [];
    const max = this.opts.maxEvidenceEpochs ?? 256;
    for (let i = 0; i < max; i++) {
      try {
        const ep = await client.fetchEvidenceEpoch(experimentId, i);
        evidence.push({
          epochIndex: i,
          rootHex: hex(ep.observationsRoot),
          file: null,
          leafCount: null,
          batches: [], // per-batch headers live in the bundle, never in an on-chain account
          cohortId: ep.cohortId ?? null,
          timeStart: big(ep.timeStart),
          timeEnd: big(ep.timeEnd),
          signerSetRootHex: hex(ep.signerSetRoot),
          observationsRootHex: hex(ep.observationsRoot),
          acceptedCount: big(ep.acceptedCount),
          rejectedCount: big(ep.rejectedCount),
          distinctSigners: big(ep.distinctSigners),
          contentHashHex: hex(ep.contentHash),
          producer: ep.producer?.toBase58?.() ?? null,
        });
      } catch {
        break;
      }
    }

    let resultArtifactHashHex: string | null = null;
    let evaluationRewardRoot: string | null = null;
    try {
      const ev = await client.fetchEvaluation(experimentId);
      resultArtifactHashHex = hex(ev.resultArtifactHash);
      evaluationRewardRoot = hex(ev.rewardRoot);
    } catch {
      // No Evaluation account yet. Not an error — the experiment has not been evaluated.
    }

    let distributionRoot: string | null = null;
    let totalAllocated: string | null = null;
    let unallocated: string | null = null;
    let claimWindowEnd: string | null = null;
    try {
      const d = await client.fetchDistribution(experimentId);
      distributionRoot = hex(d.rewardRoot);
      totalAllocated = big(d.totalAllocatedBaseUnits);
      unallocated = big(d.unallocatedBaseUnits);
      claimWindowEnd = big(d.claimWindowEnd);
    } catch {
      // Not finalized yet.
    }

    const challenges = await this.fetchChallenges(client, experimentId, warnings);

    // Off-chain artifacts, if a bundle is published for this experiment.
    let bundleSnapshot: ExperimentSnapshot | null = null;
    if (this.opts.bundleSource) {
      try {
        bundleSnapshot = await this.opts.bundleSource.loadExperiment(experimentId);
      } catch {
        warnings.push(
          "No published audit bundle reachable for this experiment. On-chain commitments are " +
            "shown; the off-chain artifacts must be obtained from the coordinator to verify.",
        );
      }
    }

    const manifest = bundleSnapshot?.experiment.manifest ?? null;
    const result = bundleSnapshot?.result ?? parseAnalysis(null);
    const onchainCommitments: OnchainCommitments = {};
    if (!isZero(hex(e.manifestHash))) onchainCommitments.manifest_hash = hex(e.manifestHash);
    if (cohortRootHex && !isZero(cohortRootHex)) onchainCommitments.cohort_root = cohortRootHex;
    const rewardRoot = distributionRoot ?? evaluationRewardRoot;
    if (rewardRoot && !isZero(rewardRoot)) onchainCommitments.reward_root = rewardRoot;
    if (resultArtifactHashHex && !isZero(resultArtifactHashHex)) {
      onchainCommitments.result_artifact_hash = resultArtifactHashHex;
    }

    return {
      source: { id: this.id, kind: this.kind, network: this.network },
      experiment: {
        experimentId,
        status,
        statusProvenance: "onchain",
        manifestHashHex: hex(e.manifestHash),
        manifest,
        revealedSeedHex: e.revealedSeed ? hex(e.revealedSeed) : null,
        cohortPublished: Boolean(e.cohortPublished),
        cohortRootHex,
        cohortCount,
        evaluationValid: Boolean(e.evaluationValid),
        openChallenges: Number(e.openChallenges ?? 0),
        aborted: Boolean(e.aborted),
        challengeWindowEnd: big(e.challengeWindowEnd),
        claimWindowEnd: big(e.claimWindowEnd),
        cluster: "devnet",
      },
      roots: bundleSnapshot?.roots ?? null,
      provenance: bundleSnapshot?.provenance ?? null,
      assignment: bundleSnapshot?.assignment ?? [],
      evidence: evidence.length > 0 ? evidence : (bundleSnapshot?.evidence ?? []),
      result,
      challenges,
      distribution: {
        present: distributionRoot !== null,
        rewardRootHex: distributionRoot ?? evaluationRewardRoot,
        totalAllocatedBaseUnits: totalAllocated,
        unallocatedBaseUnits: unallocated,
        claimWindowEnd,
        leaves: await this.markClaimed(client, experimentId, bundleSnapshot),
        leafTotalBaseUnits: bundleSnapshot?.distribution.leafTotalBaseUnits ?? null,
      },
      bundleFiles: bundleSnapshot?.bundleFiles ?? null,
      bundleUrl: this.opts.bundleUrlFor?.(experimentId) ?? bundleSnapshot?.bundleUrl ?? null,
      onchainCommitments,
      warnings,
    };
  }

  private async fetchChallenges(
    client: any,
    experimentId: string,
    warnings: string[],
  ): Promise<ChallengeView[]> {
    try {
      const [{ pda }, web3] = await Promise.all([
        import("@causal-rewards/sdk").then((m) => ({ pda: m })),
        import("@solana/web3.js"),
      ]);
      const experiment = (pda as any).experimentPda(experimentId) as InstanceType<
        typeof web3.PublicKey
      >;
      const all = await client.challenge.account.challenge.all([
        { memcmp: { offset: 8, bytes: experiment.toBase58() } },
      ]);
      return all
        .map((r: any) => {
          const a = r.account;
          const raw = Number(a.resolution ?? 0);
          return {
            challenger: a.challenger?.toBase58?.() ?? "",
            bondAmountBaseUnits: big(a.bondAmount) ?? "0",
            reasonCode: Number(a.reasonCode ?? 0),
            resolution: RESOLUTIONS[raw] ?? "unknown",
            resolutionRaw: raw,
            bondVault: a.bondVault?.toBase58?.() ?? null,
          } satisfies ChallengeView;
        })
        .sort((a: ChallengeView, b: ChallengeView) => a.challenger.localeCompare(b.challenger));
    } catch {
      warnings.push("Challenge accounts could not be enumerated from this RPC endpoint.");
      return [];
    }
  }

  /** Flag which committed reward leaves already have a single-use `ClaimReceipt` on-chain. */
  private async markClaimed(
    client: any,
    experimentId: string,
    bundleSnapshot: ExperimentSnapshot | null,
  ) {
    const leaves = bundleSnapshot?.distribution.leaves ?? [];
    const out = [];
    for (const leaf of leaves) {
      let claimed: boolean | null = null;
      try {
        await client.fetchClaimReceipt(experimentId, BigInt(leaf.leafIndex));
        claimed = true;
      } catch {
        claimed = false;
      }
      out.push({ ...leaf, claimed });
    }
    return out;
  }
}
