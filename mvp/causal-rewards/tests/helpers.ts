// Shared helpers for the Causal Rewards Protocol integration tests.
//
// The hashing / Merkle / seed-commitment / reward-leaf logic here MIRRORS the
// on-chain `crp-crypto` crate and `specs/serialization.md`. Keeping a parallel TS
// implementation lets the tests build the same roots/proofs the program verifies.

import { createHash } from "crypto";
import { PublicKey } from "@solana/web3.js";

export const REGISTRY_ID = new PublicKey(
  "8DotPgXajgeHt68htC7vbuvScUDkQa9ZPi3a5Sk1mioj"
);
export const EVIDENCE_ID = new PublicKey(
  "Ex82ncHsgc4ZFWDYQQzwR96GNNnKd3YmoULnjWgb1neP"
);
export const SETTLEMENT_ID = new PublicKey(
  "4YGzmSUZYxYQMJ4E9YiM7h8dv4KChVEKHuN5T2W5qn86"
);
export const CHALLENGE_ID = new PublicKey(
  "J9MfPYVhveHLLRnGBUiMxJqCLJP6s5ZUn7e5h3mnsG4z"
);

export function sha256(...parts: Buffer[]): Buffer {
  const h = createHash("sha256");
  for (const p of parts) h.update(p);
  return h.digest();
}

const LEAF_PREFIX = Buffer.from([0x00]);
const NODE_PREFIX = Buffer.from([0x01]);
export const DOMAIN_REWARD = Buffer.from("CRP:reward:v1", "ascii");

export function leafHash(domain: Buffer, bytes: Buffer): Buffer {
  return sha256(LEAF_PREFIX, domain, bytes);
}
export function nodeHash(l: Buffer, r: Buffer): Buffer {
  return sha256(NODE_PREFIX, l, r);
}

export function u64be(n: bigint): Buffer {
  const b = Buffer.alloc(8);
  b.writeBigUInt64BE(n);
  return b;
}
export function u64le(n: bigint): Buffer {
  const b = Buffer.alloc(8);
  b.writeBigUInt64LE(n);
  return b;
}

// PROVISIONAL M2 reward leaf: recipient(32) || amount(u64 BE) || index(u64 BE).
export function rewardLeafHash(
  recipient: PublicKey,
  amount: bigint,
  index: bigint
): Buffer {
  const content = Buffer.concat([recipient.toBuffer(), u64be(amount), u64be(index)]);
  return leafHash(DOMAIN_REWARD, content);
}

export function merkleRootFromHashes(hashes: Buffer[]): Buffer {
  if (hashes.length === 0) return Buffer.alloc(32);
  let level = hashes.slice();
  while (level.length > 1) {
    const next: Buffer[] = [];
    for (let i = 0; i < level.length; i += 2) {
      if (i + 1 < level.length) next.push(nodeHash(level[i], level[i + 1]));
      else next.push(level[i]); // promote unpaired trailing node
    }
    level = next;
  }
  return level[0];
}

export type ProofStep = { sibling: number[]; siblingIsLeft: boolean };

export function buildProof(leafHashes: Buffer[], index: number): ProofStep[] {
  const proof: ProofStep[] = [];
  let level = leafHashes.slice();
  let pos = index;
  while (level.length > 1) {
    const next: Buffer[] = [];
    for (let i = 0; i < level.length; i += 2) {
      if (i + 1 < level.length) {
        if (i === pos) proof.push({ sibling: [...level[i + 1]], siblingIsLeft: false });
        else if (i + 1 === pos) proof.push({ sibling: [...level[i]], siblingIsLeft: true });
        next.push(nodeHash(level[i], level[i + 1]));
      } else {
        next.push(level[i]);
      }
    }
    pos = Math.floor(pos / 2);
    level = next;
  }
  return proof;
}

export const SEED_COMMIT_DOMAIN = Buffer.from("CRP-seed-commit-v1", "ascii");
export function seedCommitment(seed: Buffer): Buffer {
  return sha256(SEED_COMMIT_DOMAIN, seed);
}

export function experimentIdHash(id: string): Buffer {
  return sha256(Buffer.from("CRP-exp-id", "ascii"), Buffer.from(id, "utf8"));
}

// ---- PDA helpers ----
export function pda(seeds: Buffer[], programId: PublicKey): PublicKey {
  return PublicKey.findProgramAddressSync(seeds, programId)[0];
}
export function experimentPda(idHash: Buffer): PublicKey {
  return pda([Buffer.from("experiment"), idHash], REGISTRY_ID);
}
export function protocolConfigPda(): PublicKey {
  return pda([Buffer.from("protocol_config")], REGISTRY_ID);
}
export function vaultPda(experiment: PublicKey): PublicKey {
  return pda([Buffer.from("vault"), experiment.toBuffer()], REGISTRY_ID);
}
export function vaultAuthorityPda(experiment: PublicKey): PublicKey {
  return pda([Buffer.from("vault_authority"), experiment.toBuffer()], SETTLEMENT_ID);
}
export function cohortSetPda(experiment: PublicKey): PublicKey {
  return pda([Buffer.from("cohort_set"), experiment.toBuffer()], REGISTRY_ID);
}
export function epochPda(experiment: PublicKey, index: bigint): PublicKey {
  return pda([Buffer.from("epoch"), experiment.toBuffer(), u64le(index)], EVIDENCE_ID);
}
export function evaluationPda(experiment: PublicKey): PublicKey {
  return pda([Buffer.from("evaluation"), experiment.toBuffer()], SETTLEMENT_ID);
}
export function distributionPda(experiment: PublicKey): PublicKey {
  return pda([Buffer.from("distribution"), experiment.toBuffer()], SETTLEMENT_ID);
}
export function claimReceiptPda(experiment: PublicKey, index: bigint): PublicKey {
  return pda([Buffer.from("claim"), experiment.toBuffer(), u64le(index)], SETTLEMENT_ID);
}
export function settlementCpiAuthorityPda(): PublicKey {
  return pda([Buffer.from("cpi_authority")], SETTLEMENT_ID);
}
export function challengeCpiAuthorityPda(): PublicKey {
  return pda([Buffer.from("cpi_authority")], CHALLENGE_ID);
}
export function challengePda(experiment: PublicKey, challenger: PublicKey): PublicKey {
  return pda(
    [Buffer.from("challenge"), experiment.toBuffer(), challenger.toBuffer()],
    CHALLENGE_ID
  );
}
export function bondVaultPda(challenge: PublicKey): PublicKey {
  return pda([Buffer.from("bond_vault"), challenge.toBuffer()], CHALLENGE_ID);
}

export const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
