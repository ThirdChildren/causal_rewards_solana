/**
 * Read a published audit bundle over plain HTTP (or any byte fetcher).
 *
 * This source is the offline/demo path AND the honest one: it reads exactly the artifacts a
 * third party downloads and feeds to `crp-verify`. If the bundle renders here, the same bytes
 * verify there. Chain-only facts (live status, claim receipts, challenge accounts) are absent
 * and reported as warnings rather than guessed.
 */
import {
  distributionFromBundle,
  parseAnalysis,
  parseAssignment,
  parseEvidenceEpochs,
  parseManifest,
  parseProvenance,
  parseRewardLeaves,
  parseRoots,
  readBundleJson,
} from "../bundle";
import type { BundleFiles, ExperimentStatus } from "../types";
import type {
  ExperimentSnapshot,
  ExperimentSummary,
  NetworkLabel,
  ProtocolDataSource,
} from "./types";

export type Fetcher = (url: string) => Promise<Uint8Array>;

export interface BundleIndexEntry {
  id: string;
  files: string[];
}
export interface BundleIndex {
  bundles: BundleIndexEntry[];
}

export const DEFAULT_BUNDLE_ROOT = "bundles";

export async function httpFetcher(url: string): Promise<Uint8Array> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch ${url}: ${res.status} ${res.statusText}`);
  return new Uint8Array(await res.arrayBuffer());
}

export interface BundleSourceOptions {
  /** Base URL (or path) the bundles are published under. */
  root?: string;
  fetcher?: Fetcher;
  /**
   * Status to display for a bundle-only read. A bundle carries no live chain status, so we
   * report what the artifacts prove was reached, never a state we did not observe.
   */
  assumedStatus?: ExperimentStatus;
  network?: NetworkLabel;
}

export class BundleDataSource implements ProtocolDataSource {
  readonly id = "audit-bundle";
  readonly kind = "bundle" as const;
  readonly network: NetworkLabel;

  private readonly root: string;
  private readonly fetcher: Fetcher;
  private indexCache: BundleIndex | null = null;

  constructor(opts: BundleSourceOptions = {}) {
    this.root = (opts.root ?? DEFAULT_BUNDLE_ROOT).replace(/\/+$/, "");
    this.fetcher = opts.fetcher ?? httpFetcher;
    this.network = opts.network ?? { cluster: "devnet", endpoint: null };
  }

  private url(...parts: string[]): string {
    return [this.root, ...parts].join("/");
  }

  private async index(): Promise<BundleIndex> {
    if (this.indexCache) return this.indexCache;
    const bytes = await this.fetcher(this.url("index.json"));
    this.indexCache = JSON.parse(new TextDecoder().decode(bytes)) as BundleIndex;
    return this.indexCache;
  }

  async listExperiments(): Promise<ExperimentSummary[]> {
    const idx = await this.index();
    const out: ExperimentSummary[] = [];
    for (const b of idx.bundles) {
      try {
        const files = await this.fetchFiles(b);
        const manifestRaw = readBundleJson(files, "manifest.json");
        const rootsRaw = readBundleJson(files, "roots.json");
        const manifest = manifestRaw ? parseManifest(manifestRaw) : null;
        out.push({
          experimentId: manifest?.experimentId ?? b.id,
          title: manifest?.title ?? b.id,
          status: this.statusFor(files),
          manifestHashHex: rootsRaw ? parseRoots(rootsRaw).manifestHashHex : "",
        });
      } catch {
        out.push({ experimentId: b.id, title: b.id, status: "draft", manifestHashHex: "" });
      }
    }
    return out;
  }

  /**
   * What the artifacts themselves prove. A bundle with an evaluation and a reward leaf set
   * has reached at least `Evaluating`; without them it has reached at least `Active`. We
   * never claim `Final` from a bundle — finality is an on-chain fact.
   */
  private statusFor(files: BundleFiles): ExperimentStatus {
    if (files.has("analysis.json") && files.has("rewards.parquet")) return "evaluating";
    if (files.has("assignment.parquet")) return "active";
    return "frozen";
  }

  private async fetchFiles(entry: BundleIndexEntry): Promise<BundleFiles> {
    const map = new Map<string, Uint8Array>();
    for (const rel of entry.files) {
      map.set(rel, await this.fetcher(this.url(entry.id, rel)));
    }
    return map;
  }

  private async entryFor(experimentId: string): Promise<BundleIndexEntry> {
    const idx = await this.index();
    const direct = idx.bundles.find((b) => b.id === experimentId);
    if (direct) return direct;
    for (const b of idx.bundles) {
      const bytes = await this.fetcher(this.url(b.id, "manifest.json"));
      const m = JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>;
      if (m["experiment_id"] === experimentId) return b;
    }
    throw new Error(`no published bundle for experiment "${experimentId}"`);
  }

  async loadExperiment(experimentId: string): Promise<ExperimentSnapshot> {
    const entry = await this.entryFor(experimentId);
    const files = await this.fetchFiles(entry);
    return buildSnapshotFromBundle(files, {
      sourceId: this.id,
      kind: this.kind,
      network: this.network,
      bundleUrl: this.url(entry.id),
      status: this.statusFor(files),
    });
  }
}

export interface SnapshotBuildOptions {
  sourceId: string;
  kind: "bundle" | "rpc" | "composite";
  network: NetworkLabel;
  bundleUrl: string | null;
  status: ExperimentStatus;
}

/** Shared by the HTTP source and by node-side tests/tools that already hold the bytes. */
export async function buildSnapshotFromBundle(
  files: BundleFiles,
  opts: SnapshotBuildOptions,
): Promise<ExperimentSnapshot> {
  const warnings: string[] = [];
  const manifestRaw = readBundleJson(files, "manifest.json");
  const rootsRaw = readBundleJson(files, "roots.json");
  if (!manifestRaw) warnings.push("manifest.json is missing from this bundle.");
  if (!rootsRaw) warnings.push("roots.json is missing from this bundle.");

  const manifest = manifestRaw ? parseManifest(manifestRaw) : null;
  const roots = rootsRaw ? parseRoots(rootsRaw) : null;
  const provenance = parseProvenance(readBundleJson(files, "provenance.json"));
  const analysis = parseAnalysis(readBundleJson(files, "analysis.json"));
  const assignment = await parseAssignment(files);
  const evidence = roots ? await parseEvidenceEpochs(files, roots) : [];
  const leaves = await parseRewardLeaves(files);
  const distribution = roots
    ? distributionFromBundle(roots, leaves)
    : {
        present: false,
        rewardRootHex: null,
        totalAllocatedBaseUnits: null,
        unallocatedBaseUnits: null,
        claimWindowEnd: null,
        leaves,
        leafTotalBaseUnits: null,
      };

  warnings.push(
    "Read from a published audit bundle. Live on-chain status, challenge records and claim " +
      "receipts are not part of a bundle — connect a devnet RPC source to see them.",
  );

  return {
    source: { id: opts.sourceId, kind: opts.kind, network: opts.network },
    experiment: {
      experimentId: manifest?.experimentId ?? "",
      status: opts.status,
      statusProvenance: "bundle",
      manifestHashHex: roots?.manifestHashHex ?? "",
      manifest,
      revealedSeedHex: null,
      cohortPublished: assignment.length > 0,
      cohortRootHex: roots?.assignmentRootHex ?? null,
      cohortCount: assignment.length > 0 ? assignment.length : null,
      evaluationValid: null,
      openChallenges: null,
      aborted: null,
      challengeWindowEnd: null,
      claimWindowEnd: null,
      cluster: manifest?.cluster ?? opts.network.cluster,
    },
    roots,
    provenance,
    assignment,
    evidence,
    result: analysis,
    challenges: [],
    distribution,
    bundleFiles: files,
    bundleUrl: opts.bundleUrl,
    onchainCommitments: null,
    warnings,
  };
}
