/**
 * The audit export emits an artifact, so it is held to invariant 2: the same inputs must
 * produce byte-identical output. These tests pin that, plus the two properties that make the
 * export trustworthy at all — pass-through bytes and the privacy allowlist.
 *
 * The end-to-end acceptance (unzip -> `crp-verify` -> ACCEPT) lives in
 * `scripts/verify-export.sh`, because only an independent tool can decide that question.
 */
import { describe, expect, it } from "vitest";
import { ALL_BUNDLES, loadBundleFiles } from "../test/bundles";
import { PrivacyViolation } from "../protocol/privacy";
import { buildAuditExport, EXPORT_META_DIR } from "./auditExport";
import { crc32, writeZip } from "./zip";

function input(files: ReadonlyMap<string, Uint8Array>) {
  return {
    experimentId: "env-sensors-pilot-001",
    bundleFiles: files,
    bundleUrl: "https://example.invalid/bundles/golden-happy",
    bundleLayoutVersion: "1.0.0",
    onchainCommitments: { manifest_hash: "ab".repeat(32), reward_root: "cd".repeat(32) },
  };
}

describe("audit export determinism (invariant 2)", () => {
  it.each(ALL_BUNDLES)("%s exports byte-identically across runs", async (id) => {
    const files = await loadBundleFiles(id);
    const a = buildAuditExport({ ...input(files), experimentId: id });
    const b = buildAuditExport({ ...input(files), experimentId: id });
    expect(a.bytes.length).toBeGreaterThan(0);
    expect(Array.from(a.bytes)).toEqual(Array.from(b.bytes));
    expect(a.filename).toBe(b.filename);
  });

  it("does not depend on the iteration order of the input map", async () => {
    const files = await loadBundleFiles("demo-signal");
    const forward = buildAuditExport(input(files));
    const reversed = buildAuditExport(
      input(new Map([...files.entries()].reverse())),
    );
    expect(Array.from(reversed.bytes)).toEqual(Array.from(forward.bytes));
  });

  it("stamps no wall-clock into the archive", async () => {
    const files = await loadBundleFiles("golden-happy");
    const bytes = buildAuditExport(input(files)).bytes;
    // Local file header: DOS time at +10, DOS date at +12. Both must be the fixed epoch.
    expect(bytes[10]).toBe(0);
    expect(bytes[11]).toBe(0);
    expect(bytes[12]! | (bytes[13]! << 8)).toBe(0x0021); // 1980-01-01
  });
});

describe("audit export content", () => {
  it("copies every ratified bundle file through verbatim", async () => {
    const files = await loadBundleFiles("demo-signal");
    const result = buildAuditExport(input(files));
    for (const path of files.keys()) {
      expect(result.paths).toContain(path);
    }
    // The archive stores uncompressed, so the original bytes appear literally inside it.
    const manifest = files.get("manifest.json")!;
    const hay = result.bytes;
    let found = false;
    for (let i = 0; i + manifest.length <= hay.length && !found; i++) {
      if (hay[i] === manifest[0] && hay.subarray(i, i + manifest.length).every((b, j) => b === manifest[j])) {
        found = true;
      }
    }
    expect(found).toBe(true);
  });

  it("adds only informational files, outside every hashed slot", async () => {
    const files = await loadBundleFiles("golden-happy");
    const result = buildAuditExport(input(files));
    const added = result.paths.filter((p) => !files.has(p));
    expect(added.every((p) => p.startsWith(`${EXPORT_META_DIR}/`))).toBe(true);
    expect(added).toContain(`${EXPORT_META_DIR}/README.txt`);
    expect(added).toContain(`${EXPORT_META_DIR}/onchain-commitments.json`);
  });

  it("refuses to export a path that is not a ratified bundle slot", async () => {
    const files = new Map(await loadBundleFiles("golden-happy"));
    files.set("telemetry/raw-readings.parquet", new Uint8Array([1, 2, 3]));
    const result = buildAuditExport(input(files));
    expect(result.skipped).toContain("telemetry/raw-readings.parquet");
    expect(result.paths).not.toContain("telemetry/raw-readings.parquet");
  });

  it("throws rather than exporting an empty archive", () => {
    expect(() => buildAuditExport(input(new Map()))).toThrow(/nothing to export/);
  });
});

describe("deterministic zip writer", () => {
  it("computes the standard CRC-32", () => {
    expect(crc32(new TextEncoder().encode("123456789")) >>> 0).toBe(0xcbf43926);
  });

  it("rejects a path that could escape the archive root", () => {
    const bytes = new Uint8Array([1]);
    expect(() => writeZip([{ path: "../escape", bytes }])).toThrow(/unsafe/);
    expect(() => writeZip([{ path: "/abs", bytes }])).toThrow(/unsafe/);
    expect(() => writeZip([{ path: "", bytes }])).toThrow(/must not be empty/);
  });

  it("ends with an end-of-central-directory record and no comment", () => {
    const bytes = writeZip([{ path: "a.txt", bytes: new TextEncoder().encode("hello") }]);
    const tail = bytes.subarray(bytes.length - 22);
    expect([tail[0], tail[1], tail[2], tail[3]]).toEqual([0x50, 0x4b, 0x05, 0x06]);
    expect(tail[20]! | (tail[21]! << 8)).toBe(0);
  });
});

describe("privacy gate", () => {
  it("is a hard failure, not a warning", async () => {
    const { assertCohortLevelColumns } = await import("../protocol/privacy");
    expect(() => assertCohortLevelColumns("t", ["cohort_id", "latitude"])).toThrow(
      PrivacyViolation,
    );
    expect(() => assertCohortLevelColumns("t", ["cohort_id", "device_serial"])).toThrow(
      PrivacyViolation,
    );
    expect(() =>
      assertCohortLevelColumns("t", ["cohort_id", "recipient_hex", "amount_base_units"]),
    ).not.toThrow();
  });
});
