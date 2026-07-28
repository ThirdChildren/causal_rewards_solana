/**
 * INVARIANT 5 (data minimization), enforced rather than promised.
 *
 * The dashboard displays and exports hashes, roots, cohort-level summaries and claim state.
 * It must never surface raw telemetry, exact coordinates, or personal data. A future bundle
 * that grows a `latitude` column or a `device_serial` field must FAIL loudly here instead of
 * quietly leaking through a generic table renderer or the audit export.
 *
 * Two gates:
 *  1. `assertExportablePath` — only the ratified bundle slots leave the browser.
 *  2. `assertCohortLevelColumns` — a column-name denylist over anything we tabulate or export.
 *
 * The denylist is intentionally blunt and intentionally noisy. A false positive is a spec
 * conversation; a false negative is a privacy incident.
 */

export class PrivacyViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PrivacyViolation";
  }
}

/**
 * Bundle slots defined by `bundle_layout_version` 1.0.0 (verifier-cli `bundle.py` docstring).
 * Anything not matching one of these patterns is not exported.
 */
const ALLOWED_PATH_PATTERNS: RegExp[] = [
  /^manifest\.json$/,
  /^participants\.parquet$/,
  /^assignment\.parquet$/,
  /^analysis\.json$/,
  /^rewards\.parquet$/,
  /^rewards_detail\.parquet$/,
  /^roots\.json$/,
  /^provenance\.json$/,
  /^evidence\/epoch-\d{6}\.parquet$/,
  /^evidence\/findings\.json$/,
  /^evidence\/missingness\.json$/,
];

export function isExportablePath(path: string): boolean {
  return ALLOWED_PATH_PATTERNS.some((re) => re.test(path));
}

export function assertExportablePath(path: string): void {
  if (!isExportablePath(path)) {
    throw new PrivacyViolation(
      `refusing to export "${path}": not a ratified audit-bundle slot (bundle_layout_version 1.0.0)`,
    );
  }
}

/**
 * Column-name fragments that indicate device-level or location-precise data.
 * Cohort-level identifiers (`cohort_id`), commitments (`*_hash`, `*_root`), and settlement
 * fields (`recipient_hex`, `amount_base_units`) are fine and deliberately absent here.
 */
const DENIED_COLUMN_FRAGMENTS = [
  "lat",
  "lon",
  "lng",
  "coord",
  "gps",
  "geometry",
  "wkt",
  "address",
  "street",
  "postcode",
  "zip",
  "device_id",
  "device_serial",
  "serial",
  "imei",
  "mac_addr",
  "ip_addr",
  "email",
  "phone",
  "owner_name",
  "raw_reading",
  "raw_value",
  "telemetry",
];

/** Columns that contain a denied fragment but are known-safe protocol fields. */
const COLUMN_ALLOWLIST = new Set([
  "cohort_id",
  "latency_ms", // contains no denied fragment; listed for intent, harmless
]);

export function deniedColumns(columns: readonly string[]): string[] {
  const out: string[] = [];
  for (const col of columns) {
    const c = col.toLowerCase();
    if (COLUMN_ALLOWLIST.has(c)) continue;
    if (DENIED_COLUMN_FRAGMENTS.some((frag) => c.includes(frag))) out.push(col);
  }
  return out;
}

export function assertCohortLevelColumns(source: string, columns: readonly string[]): void {
  const bad = deniedColumns(columns);
  if (bad.length > 0) {
    throw new PrivacyViolation(
      `refusing to render or export ${source}: column(s) ${bad.join(", ")} look device-level or ` +
        `location-precise. Invariant 5 allows cohort-level identifiers, hashes, roots and counts only.`,
    );
  }
}
