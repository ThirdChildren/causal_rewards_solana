/**
 * Load the REAL audit bundles from disk for tests.
 *
 * Tests read the same artifacts `crp-verify` accepts — no hand-written fixture objects. A
 * test that passes against a mock and fails against the bundle is worse than no test, and
 * the bundle shapes here are the ones the engine and the verifier actually agree on.
 */
import { readFile, readdir } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { buildSnapshotFromBundle } from "../protocol/sources/bundleSource";
import type { ExperimentSnapshot } from "../protocol/sources/types";
import type { BundleFiles, ExperimentStatus } from "../protocol/types";

const here = dirname(fileURLToPath(import.meta.url));
const dashboard = resolve(here, "..", "..");

const ROOTS = [
  join(dashboard, "fixtures", "bundles"),
  join(dashboard, "..", "verifier-cli", "fixtures", "bundles"),
];

async function walk(dir: string, base = dir): Promise<string[]> {
  const out: string[] = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, e.name);
    if (e.isDirectory()) out.push(...(await walk(full, base)));
    else if (e.isFile()) out.push(relative(base, full).split("\\").join("/"));
  }
  return out.sort();
}

export async function loadBundleFiles(id: string): Promise<BundleFiles> {
  for (const root of ROOTS) {
    try {
      const dir = join(root, id);
      const files = new Map<string, Uint8Array>();
      for (const rel of await walk(dir)) {
        files.set(rel, new Uint8Array(await readFile(join(dir, rel))));
      }
      if (files.size > 0) return files;
    } catch {
      /* try the next root */
    }
  }
  throw new Error(`no bundle "${id}" under ${ROOTS.join(", ")}`);
}

export async function loadSnapshot(
  id: string,
  status: ExperimentStatus = "evaluating",
): Promise<ExperimentSnapshot> {
  const files = await loadBundleFiles(id);
  return buildSnapshotFromBundle(files, {
    sourceId: "test-bundle",
    kind: "bundle",
    network: { cluster: "devnet", endpoint: null },
    bundleUrl: `https://example.invalid/bundles/${id}`,
    status,
  });
}

/** The bundles every test suite runs across. `demo-low-power` is the null/zero-payout case. */
export const ALL_BUNDLES = ["golden-happy", "demo-signal", "demo-null", "demo-low-power"] as const;
