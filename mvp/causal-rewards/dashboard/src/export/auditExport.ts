/**
 * Audit export — the point of the whole dashboard.
 *
 * Produces a ZIP that `crp-verify` accepts unzipped, so anyone can reproduce every root
 * without trusting this UI, the coordinator, or the evaluator.
 *
 * Two rules make that true:
 *  1. **Pass-through bytes.** Bundle files are copied verbatim. We never re-serialize JSON or
 *     rewrite Parquet: `manifest_hash` and `result_artifact_hash` are hashes over the stored
 *     canonical bytes, so a "harmless" reformat would move them.
 *  2. **No dashboard-authored artifact inside the hashed set.** The only file this dashboard
 *     adds is `dashboard-export/…`, outside every ratified slot, and it is informational.
 *     `onchain-commitments.json` is written there too, for `crp-verify --onchain`.
 *
 * Determinism: the archive is byte-identical for identical inputs (fixed timestamps, fixed
 * entry order, STORE method) — see `zip.ts` and `auditExport.test.ts`.
 */
import { assertExportablePath, isExportablePath } from "../protocol/privacy";
import type { BundleFiles } from "../protocol/types";
import type { OnchainCommitments } from "../protocol/sources/types";
import { writeZip, type ZipEntry } from "./zip";

export const EXPORT_META_DIR = "dashboard-export";

export interface AuditExportInput {
  experimentId: string;
  bundleFiles: BundleFiles;
  onchainCommitments?: OnchainCommitments | null;
  /** Public, content-addressed location of the same bundle. Recorded in the README. */
  bundleUrl?: string | null;
  /** Bundle layout version as published in roots.json. */
  bundleLayoutVersion?: string | null;
}

export interface AuditExportResult {
  filename: string;
  bytes: Uint8Array;
  /** Paths written into the archive, in archive order. */
  paths: string[];
  /** Paths present in the source bundle that were refused by the privacy allowlist. */
  skipped: string[];
}

function sortPaths(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

const README = (input: AuditExportInput, paths: string[]): string =>
  [
    "Causal Rewards Protocol — audit bundle export",
    "=============================================",
    "",
    `experiment_id: ${input.experimentId}`,
    `bundle_layout_version: ${input.bundleLayoutVersion ?? "unknown"}`,
    `published_bundle: ${input.bundleUrl ?? "(not recorded by this export)"}`,
    "",
    "This archive is a copy, not an origin. The dashboard that produced it is a convenience",
    "layer; if it disappears, verification is unaffected. Every file below is byte-identical",
    "to the published, content-addressed bundle.",
    "",
    "Verify it yourself",
    "------------------",
    "",
    "  unzip <this-file>.zip -d bundle/",
    "  pip install crp-verifier            # or: pip install -e verifier-cli/",
    "  crp-verify bundle/ \\",
    `    --onchain bundle/${EXPORT_META_DIR}/onchain-commitments.json`,
    "",
    "Add --seed <64-hex> (the on-chain revealed assignment seed) to additionally check that",
    "every cohort arm was derived from the committed seed — freeze-before-reveal, invariant 1.",
    "",
    "Exit code 0 means every root was reproduced. The verifier treats roots.json as an",
    "untrusted claim and recomputes it; it needs no network access and no trust in the",
    "coordinator, the evaluator, or this dashboard.",
    "",
    "What a passing verification does and does not mean",
    "--------------------------------------------------",
    "",
    "It means the published artifacts are internally consistent and match the commitments",
    "anchored on Solana devnet: the manifest was frozen before the reveal, the analysis ran",
    "on the anchored evidence, and the reward leaves are the ones the reward root commits.",
    "",
    "It does NOT mean the causal effect is true. The chain verifies process, not physical",
    "truth. The estimate is only as valid as the frozen design, the data, and the assumptions",
    "recorded in the manifest.",
    "",
    "Files in this archive",
    "---------------------",
    "",
    ...paths.map((p) => `  ${p}`),
    "",
  ].join("\n");

/**
 * Build the export archive. Deterministic: no clock, no RNG, no iteration-order dependence.
 */
export function buildAuditExport(input: AuditExportInput): AuditExportResult {
  const enc = new TextEncoder();
  const allPaths = [...input.bundleFiles.keys()].sort(sortPaths);
  const kept = allPaths.filter(isExportablePath);
  const skipped = allPaths.filter((p) => !isExportablePath(p));

  if (kept.length === 0) {
    throw new Error("nothing to export: no ratified audit-bundle files in this snapshot");
  }

  const entries: ZipEntry[] = [];
  for (const path of kept) {
    assertExportablePath(path); // belt and braces: invariant 5 checked at the write boundary
    entries.push({ path, bytes: input.bundleFiles.get(path)! });
  }

  const meta: ZipEntry[] = [];
  if (input.onchainCommitments && Object.keys(input.onchainCommitments).length > 0) {
    const ordered: Record<string, string> = {};
    for (const k of Object.keys(input.onchainCommitments).sort(sortPaths)) {
      const v = (input.onchainCommitments as Record<string, string | undefined>)[k];
      if (typeof v === "string") ordered[k] = v;
    }
    meta.push({
      path: `${EXPORT_META_DIR}/onchain-commitments.json`,
      bytes: enc.encode(JSON.stringify(ordered, null, 2) + "\n"),
    });
  }

  const paths = [...entries.map((e) => e.path), ...meta.map((e) => e.path), `${EXPORT_META_DIR}/README.txt`];
  meta.push({
    path: `${EXPORT_META_DIR}/README.txt`,
    bytes: enc.encode(README(input, paths.slice().sort(sortPaths))),
  });
  meta.sort((a, b) => sortPaths(a.path, b.path));

  const bytes = writeZip([...entries, ...meta]);
  return {
    filename: `crp-audit-bundle_${safeName(input.experimentId)}.zip`,
    bytes,
    paths: [...entries, ...meta].map((e) => e.path),
    skipped,
  };
}

function safeName(id: string): string {
  return id.replace(/[^A-Za-z0-9._-]/g, "-") || "experiment";
}

/** Trigger a browser download. Split out so `buildAuditExport` stays pure and testable. */
export function downloadAuditExport(result: AuditExportResult): void {
  const view = new Uint8Array(result.bytes);
  const blob = new Blob([view.buffer as ArrayBuffer], { type: "application/zip" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = result.filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
