/**
 * Domain-separated binary Merkle tree — TypeScript leg of serialization.md §6.
 *
 * Byte-identical to `verifier-cli/reference/merkle.py` and the on-chain
 * `crp-crypto` crate:
 *   leaf_hash(i) = SHA-256( 0x00 || DOMAIN_TAG || canonical_leaf_bytes )
 *   node_hash    = SHA-256( 0x01 || left || right )
 *   odd trailing node is PROMOTED unchanged (NOT duplicated; §6.3, CVE-2012-2459).
 *   empty-tree root = 32 zero bytes (§6.4).
 */

import { sha256 } from "./canonical";

export const LEAF_PREFIX = new Uint8Array([0x00]);
export const NODE_PREFIX = new Uint8Array([0x01]);
export const EMPTY_ROOT = new Uint8Array(32); // 32 zero bytes

// Per-tree domain tags (ASCII), distinct by construction (§6.1).
const ENC = new TextEncoder();
export const DOMAIN_PARTICIPANT = ENC.encode("CRP:participant:v1");
export const DOMAIN_ASSIGNMENT = ENC.encode("CRP:assignment:v1");
export const DOMAIN_EVIDENCE = ENC.encode("CRP:evidence:v1");
export const DOMAIN_REWARD = ENC.encode("CRP:reward:v1");

/** `leaf_hash = SHA-256( 0x00 || DOMAIN_TAG || canonical_leaf_bytes )` (§6.1). */
export function leafHash(domain: Uint8Array, canonicalBytes: Uint8Array): Uint8Array {
  return sha256(LEAF_PREFIX, domain, canonicalBytes);
}

/** `node_hash = SHA-256( 0x01 || left || right )` (§6.1). */
export function nodeHash(left: Uint8Array, right: Uint8Array): Uint8Array {
  return sha256(NODE_PREFIX, left, right);
}

/**
 * Reduce an ORDERED list of leaf hashes to the Merkle root (promotion on odd
 * count, §6.3). The caller must have placed the leaves in the tree's canonical
 * order already; this never reorders.
 */
export function merkleRootFromHashes(leafHashes: Uint8Array[]): Uint8Array {
  if (leafHashes.length === 0) return EMPTY_ROOT;
  let level = leafHashes.slice();
  while (level.length > 1) {
    const next: Uint8Array[] = [];
    for (let i = 0; i < level.length; i += 2) {
      if (i + 1 < level.length) next.push(nodeHash(level[i], level[i + 1]));
      else next.push(level[i]); // promote unpaired trailing node (§6.3)
    }
    level = next;
  }
  return level[0];
}

/**
 * Build the Merkle root from an ORDERED list of already-canonical leaf byte
 * strings under `domain`. Caller owns ordering (§6.2/§6.5/§6.6).
 */
export function merkleRoot(orderedLeafBytes: Uint8Array[], domain: Uint8Array): Uint8Array {
  if (orderedLeafBytes.length === 0) return EMPTY_ROOT;
  return merkleRootFromHashes(orderedLeafBytes.map((lb) => leafHash(domain, lb)));
}

/** One step of a Merkle inclusion proof (mirrors on-chain `ClaimProofStep`). */
export interface ProofStep {
  /** 32-byte sibling hash. */
  sibling: Uint8Array;
  /**
   * true  => sibling is the LEFT node (self is the right child);
   * false => sibling is the RIGHT node (self is the left child).
   */
  siblingIsLeft: boolean;
}

/**
 * Produce the inclusion proof for `index` from an ORDERED list of leaf hashes.
 * Promotion levels contribute NO proof step (§6.3), matching
 * `crp-crypto::build_proof` and the on-chain `verify_proof` fold.
 */
export function buildProof(leafHashes: Uint8Array[], index: number): ProofStep[] {
  if (index < 0 || index >= leafHashes.length) {
    throw new RangeError(`leaf index ${index} out of range [0, ${leafHashes.length})`);
  }
  const proof: ProofStep[] = [];
  let level = leafHashes.slice();
  let pos = index;
  while (level.length > 1) {
    const next: Uint8Array[] = [];
    for (let i = 0; i < level.length; i += 2) {
      if (i + 1 < level.length) {
        if (i === pos) proof.push({ sibling: level[i + 1], siblingIsLeft: false });
        else if (i + 1 === pos) proof.push({ sibling: level[i], siblingIsLeft: true });
        next.push(nodeHash(level[i], level[i + 1]));
      } else {
        next.push(level[i]); // promoted node: no proof step
      }
    }
    pos = Math.floor(pos / 2);
    level = next;
  }
  return proof;
}

/**
 * Verify a Merkle inclusion proof by folding `leafHash` up through `proof` and
 * comparing to `root`. Identical fold to on-chain `crp-crypto::verify_proof`.
 */
export function verifyProof(
  leafHash: Uint8Array,
  proof: ProofStep[],
  root: Uint8Array,
): boolean {
  let computed = leafHash;
  for (const step of proof) {
    computed = step.siblingIsLeft
      ? nodeHash(step.sibling, computed)
      : nodeHash(computed, step.sibling);
  }
  return bytesEqual(computed, root);
}

/** Constant-shape byte-array equality. */
export function bytesEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}
