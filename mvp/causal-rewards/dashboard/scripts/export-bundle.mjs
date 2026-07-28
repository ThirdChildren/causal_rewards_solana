#!/usr/bin/env node
/**
 * Run the dashboard's REAL export path from the command line and write the archive to disk.
 *
 * This is the acceptance harness for the export: the bytes it produces come from
 * `src/export/auditExport.ts`, the same module the browser button calls — no parallel
 * implementation, no re-serialisation. `make verify-export` (see README) unzips the result
 * and runs `crp-verify` over it, which is the only thing that decides whether the export is
 * correct.
 *
 * It also proves determinism the cheap way: it builds the archive twice in one process and
 * refuses to write if the two byte strings differ (invariant 2).
 *
 *   node scripts/export-bundle.mjs [bundle-id] [--out dist-export]
 */
import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { createServer } from "vite";

const here = dirname(fileURLToPath(import.meta.url));
const dashboard = resolve(here, "..");

// Load the module through Vite so the CLI runs the EXACT source the browser bundles —
// same resolution, same aliases, no compiled copy that could drift from the UI.
const vite = await createServer({
  root: dashboard,
  server: { middlewareMode: true },
  appType: "custom",
  logLevel: "warn",
});
const { buildAuditExport } = await vite.ssrLoadModule("/src/export/auditExport.ts");

const args = process.argv.slice(2);
const outFlag = args.indexOf("--out");
const outDir = resolve(dashboard, outFlag >= 0 ? args[outFlag + 1] : "dist-export");
const bundleId = args.find((a) => !a.startsWith("--") && a !== args[outFlag + 1]) ?? "golden-happy";

const roots = [
  join(dashboard, "public", "bundles"),
  join(dashboard, "fixtures", "bundles"),
  join(dashboard, "..", "verifier-cli", "fixtures", "bundles"),
];

async function walk(dir, base = dir) {
  const out = [];
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, e.name);
    if (e.isDirectory()) out.push(...(await walk(full, base)));
    else if (e.isFile()) out.push(relative(base, full).split("\\").join("/"));
  }
  return out.sort();
}

let bundleDir = null;
for (const r of roots) {
  try {
    const files = await readdir(join(r, bundleId));
    if (files.length > 0) {
      bundleDir = join(r, bundleId);
      break;
    }
  } catch {
    /* try the next root */
  }
}
if (!bundleDir) {
  console.error(`export-bundle: no bundle "${bundleId}" under ${roots.join(", ")}`);
  process.exit(1);
}

const files = new Map();
for (const rel of await walk(bundleDir)) {
  files.set(rel, new Uint8Array(await readFile(join(bundleDir, rel))));
}

const manifest = files.has("manifest.json")
  ? JSON.parse(new TextDecoder().decode(files.get("manifest.json")))
  : {};
const rootsJson = files.has("roots.json")
  ? JSON.parse(new TextDecoder().decode(files.get("roots.json")))
  : {};

const input = {
  experimentId: manifest.experiment_id ?? bundleId,
  bundleFiles: files,
  bundleUrl: `https://example.invalid/bundles/${bundleId}`,
  bundleLayoutVersion: rootsJson.bundle_layout_version ?? null,
  onchainCommitments: {
    manifest_hash: rootsJson.manifest_hash,
    assignment_root: rootsJson.roots?.assignment_root_hex,
    reward_root: rootsJson.roots?.reward_root_hex,
    result_artifact_hash: rootsJson.roots?.result_artifact_hash,
  },
};

const a = buildAuditExport(input);
const b = buildAuditExport(input);
const ha = createHash("sha256").update(a.bytes).digest("hex");
const hb = createHash("sha256").update(b.bytes).digest("hex");
if (ha !== hb) {
  console.error(`export-bundle: NON-DETERMINISTIC export (${ha} != ${hb})`);
  process.exit(1);
}

await mkdir(outDir, { recursive: true });
const outPath = join(outDir, a.filename);
await writeFile(outPath, a.bytes);

console.log(`bundle      ${bundleDir}`);
console.log(`archive     ${outPath}`);
console.log(`sha256      ${ha}  (identical across two builds)`);
console.log(`entries     ${a.paths.length}`);
for (const p of a.paths) console.log(`            ${p}`);
if (a.skipped.length > 0) {
  console.log(`skipped     ${a.skipped.join(", ")}  (not a ratified bundle slot)`);
}

await vite.close();
