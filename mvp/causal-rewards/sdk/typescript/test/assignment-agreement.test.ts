/**
 * M2 CROSS-IMPL AGREEMENT GATE.
 *
 * This suite runs WITHOUT a validator. It asserts the SDK's canonical crypto
 * (specs/serialization.md §6–§7) reproduces, byte-for-byte, every published golden:
 *
 *   - all 11 assignment roots in `test-vectors/assignment/` — plus, for each, the
 *     seed commitment, every per-cohort `prf_u64`, and every canonical leaf's bytes
 *     and hash (the full §7 derivation, not just the final root);
 *   - the §6.6 reward-leaf content layout + `leaf_hash` (BigInt / big-endian).
 *
 * The SDK is the third leg of agreement behind `crp-crypto` and the verifier
 * reference. Any single divergence here is an SDK bug (Invariant 2, determinism).
 */

import { readdirSync, readFileSync } from "fs";
import { join } from "path";
import { expect } from "chai";
import { PublicKey } from "@solana/web3.js";

import {
  seedCommitment,
  cohortPrf,
  deriveAssignment,
  assignmentLeafBytes,
  assignmentRoot,
  buildAssignmentRoot,
  AssignmentDesign,
  toHex,
  fromHex,
  leafHash,
  DOMAIN_REWARD,
} from "../src/crypto";
import { rewardLeafContent, rewardLeafHash } from "../src/crypto/reward";

const VECTORS_DIR = join(__dirname, "..", "..", "..", "test-vectors", "assignment");

interface VectorInputs {
  experiment_id: string;
  seed_hex: string;
  cohort_ids: string[];
  design: "bernoulli" | "fixed_count";
  params: { treat_fraction_ppm?: string; treatment_count?: string };
}

interface Vector {
  name: string;
  inputs: VectorInputs;
  step1_seed_commitment: { seed_commitment_hex: string };
  step2_cohort_prf: { values: Array<{ cohort_id: string; prf_u64: string }> };
  step4_leaves: {
    leaves: Array<{
      cohort_id: string;
      arm: string;
      leaf_canonical_bytes_hex: string;
      leaf_hash_hex: string;
    }>;
  };
  step5_assignment_root: { assignment_root_hex: string };
}

function designOf(v: VectorInputs): AssignmentDesign {
  if (v.design === "bernoulli") {
    return { kind: "bernoulli", treatFractionPpm: BigInt(v.params.treat_fraction_ppm!) };
  }
  return { kind: "fixed_count", treatmentCount: Number(v.params.treatment_count!) };
}

function loadVectors(): Vector[] {
  return readdirSync(VECTORS_DIR)
    .filter((d) => d.startsWith("assign-"))
    .sort()
    .map((d) => JSON.parse(readFileSync(join(VECTORS_DIR, d, "vector.json"), "utf8")) as Vector);
}

describe("assignment-root agreement (11 golden vectors, §7)", () => {
  const vectors = loadVectors();

  it("loads exactly 11 golden vectors", () => {
    expect(vectors.length).to.equal(11);
  });

  for (const v of vectors) {
    describe(v.name, () => {
      const seed = fromHex(v.inputs.seed_hex);

      it("reproduces the seed commitment (§7.2, salt-free)", () => {
        expect(toHex(seedCommitment(seed))).to.equal(v.step1_seed_commitment.seed_commitment_hex);
      });

      it("reproduces every per-cohort prf_u64 (§7.3, big-endian u64)", () => {
        for (const row of v.step2_cohort_prf.values) {
          const prf = cohortPrf(seed, v.inputs.experiment_id, row.cohort_id);
          expect(prf.toString(), row.cohort_id).to.equal(row.prf_u64);
        }
      });

      it("reproduces every canonical leaf's bytes + hash, in canonical order (§7.5)", () => {
        const assignments = deriveAssignment(
          seed,
          v.inputs.experiment_id,
          v.inputs.cohort_ids,
          designOf(v.inputs),
        );
        // Canonical (cohort_id ascending) order must match the golden leaf order.
        expect(assignments.map((a) => a.cohortId)).to.deep.equal(
          v.step4_leaves.leaves.map((l) => l.cohort_id),
        );
        assignments.forEach((a, i) => {
          const golden = v.step4_leaves.leaves[i];
          expect(a.arm, `${golden.cohort_id} arm`).to.equal(golden.arm);
          expect(toHex(assignmentLeafBytes(a)), `${golden.cohort_id} bytes`).to.equal(
            golden.leaf_canonical_bytes_hex,
          );
          expect(toHex(leafHashFor(a)), `${golden.cohort_id} leaf_hash`).to.equal(
            golden.leaf_hash_hex,
          );
        });
      });

      it("reproduces the assignment Merkle root (§6)", () => {
        const { root } = buildAssignmentRoot(
          seed,
          v.inputs.experiment_id,
          v.inputs.cohort_ids,
          designOf(v.inputs),
        );
        expect(toHex(root)).to.equal(v.step5_assignment_root.assignment_root_hex);
      });

      it("is order-independent: scrambled cohort input yields the same root", () => {
        const scrambled = [...v.inputs.cohort_ids].reverse();
        const a = assignmentRoot(
          deriveAssignment(seed, v.inputs.experiment_id, v.inputs.cohort_ids, designOf(v.inputs)),
        );
        const b = assignmentRoot(
          deriveAssignment(seed, v.inputs.experiment_id, scrambled, designOf(v.inputs)),
        );
        expect(toHex(a)).to.equal(toHex(b));
      });
    });
  }
});

// Local helper mirroring assignment.ts leaf hashing via the assignment domain.
import { DOMAIN_ASSIGNMENT } from "../src/crypto/merkle";
import type { CohortAssignment } from "../src/crypto/assignment";
function leafHashFor(a: CohortAssignment): Uint8Array {
  return leafHash(DOMAIN_ASSIGNMENT, assignmentLeafBytes(a));
}

describe("reward-leaf form (§6.6, BigInt / big-endian)", () => {
  it("G1: zero recipient, amount 1_000_000, index 0", () => {
    const r = new PublicKey(new Uint8Array(32));
    expect(toHex(rewardLeafContent(r, 1_000_000n, 0n))).to.equal(
      "000000000000000000000000000000000000000000000000000000000000000000000000000f42400000000000000000",
    );
    expect(toHex(rewardLeafHash(r, 1_000_000n, 0n))).to.equal(
      "773b50b6ed5cae07514020415a7bb3a3336be1eca7070b40bd5774120c2db299",
    );
  });

  it("G2: 0x01… recipient, amount u64::MAX, index 5 (exercises full u64 width)", () => {
    const r = new PublicKey(new Uint8Array(32).fill(1));
    const uMax = (1n << 64n) - 1n;
    expect(toHex(rewardLeafContent(r, uMax, 5n))).to.equal(
      "0101010101010101010101010101010101010101010101010101010101010101ffffffffffffffff0000000000000005",
    );
    expect(toHex(rewardLeafHash(r, uMax, 5n))).to.equal(
      "4d222f05e9cf34a89775de42ab3647281eba236546ed7a15f95728a5264eacc2",
    );
  });

  it("uses the reward domain tag CRP:reward:v1", () => {
    expect(new TextDecoder().decode(DOMAIN_REWARD)).to.equal("CRP:reward:v1");
  });
});
