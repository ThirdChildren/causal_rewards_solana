/**
 * Deterministic seed commitment + cohort-assignment derivation — TypeScript leg of
 * serialization.md §7 (RATIFIED). Byte-identical to
 * `verifier-cli/reference/assignment.py` and `crp-crypto`.
 *
 * Freeze-before-reveal (Invariant 1): the frozen manifest commits
 * `seed_commitment(seed)`; the seed is revealed later. Verification is two steps:
 *   1. commitment check:  seedCommitment(revealedSeed) == frozenCommitment
 *   2. derivation:        deriveAssignment(revealedSeed, experimentId, cohorts, design)
 * Both are pure functions of committed/revealed inputs: no wall-clock, no unseeded
 * RNG, no float (Invariant 2).
 */

import { sha256 } from "./canonical";
import {
  canonicalJsonBytes,
  CJsonValue,
} from "./canonical";
import { DOMAIN_ASSIGNMENT, merkleRoot } from "./merkle";

const ENC = new TextEncoder();

/** The assignment seed is exactly 32 bytes (§7.1). */
export const SEED_LEN = 32;
export const SEED_COMMIT_DOMAIN = ENC.encode("CRP-seed-commit-v1"); // §7.2
export const ASSIGN_PRF_DOMAIN = ENC.encode("CRP-assign-v1"); // §7.3

export const ARM_TREATMENT = "treatment";
export const ARM_CONTROL = "control";
export type Arm = typeof ARM_TREATMENT | typeof ARM_CONTROL;

const PPM = 1_000_000n;

/**
 * `seed_commitment = SHA-256( "CRP-seed-commit-v1" || seed )` — NO salt (§7.2).
 * This is exactly what `freeze_experiment` stores and `reveal_seed` re-checks
 * on-chain. Compute it from a locally-generated seed to obtain the commitment
 * you freeze BEFORE ever revealing the seed (Invariant 1).
 */
export function seedCommitment(seed: Uint8Array): Uint8Array {
  if (seed.length !== SEED_LEN) {
    throw new Error(`seed must be exactly ${SEED_LEN} bytes, got ${seed.length}`);
  }
  return sha256(SEED_COMMIT_DOMAIN, seed);
}

function u32be(n: number): Uint8Array {
  if (n < 0 || n > 0xffffffff) throw new RangeError(`length out of u32 range: ${n}`);
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, n, false); // big-endian
  return b;
}

/**
 * Per-cohort PRF (§7.3), length-prefixed so no two (experimentId, cohortId) pairs
 * can collide via naive concatenation:
 *   msg = "CRP-assign-v1" || seed || u32be(len(exp)) || exp || u32be(len(coh)) || coh
 *   prf_u64 = big-endian uint64 of SHA-256(msg)[0..8]
 * Returned as a `bigint` so all 64 bits are exact (JS `number` cannot hold u64).
 */
export function cohortPrf(seed: Uint8Array, experimentId: string, cohortId: string): bigint {
  if (seed.length !== SEED_LEN) {
    throw new Error(`seed must be exactly ${SEED_LEN} bytes, got ${seed.length}`);
  }
  const exp = ENC.encode(experimentId);
  const coh = ENC.encode(cohortId);
  const digest = sha256(ASSIGN_PRF_DOMAIN, seed, u32be(exp.length), exp, u32be(coh.length), coh);
  return new DataView(digest.buffer, digest.byteOffset, 8).getBigUint64(0, false); // big-endian
}

export interface CohortAssignment {
  cohortId: string;
  arm: Arm;
  /** Auditable PRF intermediate; NOT part of any leaf preimage (§7.5). */
  prfU64: bigint;
}

/** Supported assignment designs (§7.4). Others are an M2 open item upstream. */
export type AssignmentDesign =
  | { kind: "bernoulli"; treatFractionPpm: bigint | number }
  | { kind: "fixed_count"; treatmentCount: number };

/**
 * UTF-16 code-unit comparator (matches the reference `encode('utf-16-be')` sort
 * and `crp-crypto`'s `utf16be_key`). JS string `<` compares by UTF-16 code unit,
 * which coincides with UTF-16-BE byte order.
 */
function utf16Cmp(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Derive per-cohort arms deterministically (§7.4). `cohortIds` may be supplied in
 * ANY order; the result is returned in canonical leaf order (cohortId ascending by
 * UTF-16 code unit) and is independent of input order.
 */
export function deriveAssignment(
  seed: Uint8Array,
  experimentId: string,
  cohortIds: string[],
  design: AssignmentDesign,
): CohortAssignment[] {
  if (new Set(cohortIds).size !== cohortIds.length) {
    throw new Error("duplicate cohort_id in cohort set");
  }
  const prf = new Map<string, bigint>();
  for (const cid of cohortIds) prf.set(cid, cohortPrf(seed, experimentId, cid));

  const arm = new Map<string, Arm>();
  if (design.kind === "bernoulli") {
    const ppm = BigInt(design.treatFractionPpm);
    if (ppm < 0n || ppm > PPM) throw new RangeError(`treat_fraction_ppm out of range: ${ppm}`);
    for (const cid of cohortIds) {
      arm.set(cid, prf.get(cid)! % PPM < ppm ? ARM_TREATMENT : ARM_CONTROL);
    }
  } else if (design.kind === "fixed_count") {
    const k = design.treatmentCount;
    if (k < 0 || k > cohortIds.length) throw new RangeError(`treatment_count out of range: ${k}`);
    // Rank by (prf_u64, cohort_id) ascending; the first k are treatment (§7.4).
    const ranked = cohortIds.slice().sort((a, b) => {
      const pa = prf.get(a)!;
      const pb = prf.get(b)!;
      if (pa < pb) return -1;
      if (pa > pb) return 1;
      return utf16Cmp(a, b);
    });
    const treated = new Set(ranked.slice(0, k));
    for (const cid of cohortIds) arm.set(cid, treated.has(cid) ? ARM_TREATMENT : ARM_CONTROL);
  } else {
    throw new Error(`unknown design: ${(design as { kind: string }).kind}`);
  }

  // Canonical leaf order: cohort_id ascending (UTF-16 code unit).
  const ordered = cohortIds.slice().sort(utf16Cmp);
  return ordered.map((cid) => ({ cohortId: cid, arm: arm.get(cid)!, prfU64: prf.get(cid)! }));
}

/** Canonical assignment leaf object (§7.5): only the committed decision. */
export function assignmentLeafObject(a: CohortAssignment): CJsonValue {
  return { arm: a.arm, cohort_id: a.cohortId };
}

/** Canonical assignment leaf bytes = CJSON({"arm":..,"cohort_id":..}) (§7.5). */
export function assignmentLeafBytes(a: CohortAssignment): Uint8Array {
  return canonicalJsonBytes(assignmentLeafObject(a));
}

/**
 * Compute the assignment Merkle root from a derived (canonically-ordered)
 * assignment list. This is the `cohort_root` published on-chain by
 * `publish_cohort_root` and re-derived by the verifier.
 */
export function assignmentRoot(assignments: CohortAssignment[]): Uint8Array {
  return merkleRoot(assignments.map(assignmentLeafBytes), DOMAIN_ASSIGNMENT);
}

/**
 * One-shot builder: derive assignments from a revealed seed + cohort list + design
 * and return both the ordered assignments and the assignment root.
 */
export function buildAssignmentRoot(
  seed: Uint8Array,
  experimentId: string,
  cohortIds: string[],
  design: AssignmentDesign,
): { assignments: CohortAssignment[]; root: Uint8Array } {
  const assignments = deriveAssignment(seed, experimentId, cohortIds, design);
  return { assignments, root: assignmentRoot(assignments) };
}
