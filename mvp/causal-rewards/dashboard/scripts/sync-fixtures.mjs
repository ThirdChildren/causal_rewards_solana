#!/usr/bin/env node
/**
 * Copy the REAL verified audit bundles from `verifier-cli/fixtures/bundles/` into
 * `dashboard/public/bundles/` so the dashboard is developable and demoable with zero
 * network access, against artifacts that `crp-verify` already accepts.
 *
 * This is a read-only copy. `verifier-cli/` is owned by another component; nothing here
 * writes into it. The copy is gitignored — it is a build input, never a source of truth.
 */
import { cp, mkdir, readdir, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dashboardDir = resolve(here, "..");
const repoRoot = resolve(dashboardDir, "..");
const srcRoots = [
  join(repoRoot, "verifier-cli", "fixtures", "bundles"),
  join(dashboardDir, "fixtures", "bundles"),
];
const dstRoot = join(dashboardDir, "public", "bundles");

async function isDir(p) {
  try {
    return (await stat(p)).isDirectory();
  } catch {
    return false;
  }
}

/** Every file under `dir`, as POSIX-relative paths, sorted (deterministic index). */
async function walk(dir, base = dir) {
  const out = [];
  for (const entry of (await readdir(dir, { withFileTypes: true })).sort((a, b) =>
    a.name < b.name ? -1 : a.name > b.name ? 1 : 0,
  )) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...(await walk(full, base)));
    else if (entry.isFile()) out.push(relative(base, full).split("\\").join("/"));
  }
  return out.sort();
}

await rm(dstRoot, { recursive: true, force: true });
await mkdir(dstRoot, { recursive: true });

const bundles = [];
for (const srcRoot of srcRoots) {
  if (!(await isDir(srcRoot))) {
    console.error(`sync-fixtures: no bundles at ${srcRoot} — skipping.`);
    continue;
  }
  for (const entry of (await readdir(srcRoot, { withFileTypes: true })).sort((a, b) =>
    a.name < b.name ? -1 : 1,
  )) {
    if (!entry.isDirectory()) continue;
    const src = join(srcRoot, entry.name);
    const dst = join(dstRoot, entry.name);
    await cp(src, dst, { recursive: true });
    const files = await walk(dst);
    bundles.push({ id: entry.name, files });
    console.log(`sync-fixtures: ${entry.name} (${files.length} files)`);
  }
}
bundles.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

// A static index so the browser can enumerate bundle contents without directory listing.
await writeFile(
  join(dstRoot, "index.json"),
  JSON.stringify({ bundles }, null, 2) + "\n",
  "utf8",
);
console.log(`sync-fixtures: wrote ${join(dstRoot, "index.json")}`);
