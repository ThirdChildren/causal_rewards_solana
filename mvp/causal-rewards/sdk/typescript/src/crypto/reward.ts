/**
 * Reward tree — TypeScript leg of serialization.md §6.6 (RATIFIED). Byte-identical
 * to `crp-crypto::reward_leaf_content` / `reward_leaf_hash` and the on-chain
 * settlement `claim_reward` verifier.
 *
 * A reward leaf is a FIXED-WIDTH RAW-BYTE structure (NOT CJSON): §2/§3 do not apply
 * to it; the §6.1 node formulas do.
 *
 *   recipient          : 32 raw bytes  (recipient ed25519 pubkey, native form)
 *   amount_base_units  :  8 bytes, u64 BIG-ENDIAN (mint-native base units, scale 1)
 *   leaf_index         :  8 bytes, u64 BIG-ENDIAN (0-based tree position / nullifier key)
 *
 *   reward_leaf_content = recipient || amount_be || index_be           (48 bytes)
 *   leaf_hash           = SHA-256( 0x00 || "CRP:reward:v1" || content ) (62-byte preimage)
 *
 * Amounts and indices are carried as `bigint` everywhere — a JS `number` cannot
 * hold a u64 exactly, and the big-endian encoding must be exact (Invariant 2).
 */

import { PublicKey } from "@solana/web3.js";
import {
  DOMAIN_REWARD,
  ProofStep,
  buildProof,
  leafHash,
  merkleRootFromHashes,
} from "./merkle";

const U64_MAX = (1n << 64n) - 1n;

function u64be(n: bigint): Uint8Array {
  if (n < 0n || n > U64_MAX) throw new RangeError(`u64 out of range: ${n}`);
  const b = new Uint8Array(8);
  new DataView(b.buffer).setBigUint64(0, n, false); // big-endian
  return b;
}

/** A single reward entry produced by the Stage-2 reward compiler (reward-policy.md). */
export interface RewardLeaf {
  recipient: PublicKey;
  amountBaseUnits: bigint;
  /** 0-based tree position; also the on-chain nullifier key. Assigned by ordering. */
  leafIndex: bigint;
}

/** The 48-byte fixed-width reward leaf content (§6.6). */
export function rewardLeafContent(
  recipient: PublicKey,
  amountBaseUnits: bigint,
  leafIndex: bigint,
): Uint8Array {
  const out = new Uint8Array(48);
  out.set(recipient.toBytes(), 0);
  out.set(u64be(amountBaseUnits), 32);
  out.set(u64be(leafIndex), 40);
  return out;
}

/** `leaf_hash = SHA-256( 0x00 || "CRP:reward:v1" || content )` (§6.6). */
export function rewardLeafHash(
  recipient: PublicKey,
  amountBaseUnits: bigint,
  leafIndex: bigint,
): Uint8Array {
  return leafHash(DOMAIN_REWARD, rewardLeafContent(recipient, amountBaseUnits, leafIndex));
}

/**
 * Assign `leaf_index` to a set of (recipient, amount) reward entries per the §6.6
 * PINNED primary rank key: ascending by `recipient` (unsigned big-endian 32-byte
 * compare, i.e. sol_memcmp order), then ascending by `amount_base_units`. The
 * 0-based rank IS the `leaf_index`, contiguous from 0 with no gaps.
 *
 * NOTE: §6.6 leaves an M3 residual — the tie-break when (recipient, amount) is not
 * unique is a reward-compiler (reward-policy.md) decision that must be pinned there
 * before the first reward golden root is committed. This helper therefore REJECTS a
 * duplicate (recipient, amount) pair rather than guessing an order that could
 * diverge from the compiler. Pass already-indexed leaves to `rewardRoot` if your
 * compiler emits its own indices.
 */
export function assignLeafIndices(
  entries: Array<{ recipient: PublicKey; amountBaseUnits: bigint }>,
): RewardLeaf[] {
  const sorted = entries.slice().sort((a, b) => {
    const cmp = compareBytes(a.recipient.toBytes(), b.recipient.toBytes());
    if (cmp !== 0) return cmp;
    if (a.amountBaseUnits < b.amountBaseUnits) return -1;
    if (a.amountBaseUnits > b.amountBaseUnits) return 1;
    return 0;
  });
  for (let i = 1; i < sorted.length; i++) {
    const prev = sorted[i - 1];
    const cur = sorted[i];
    if (
      compareBytes(prev.recipient.toBytes(), cur.recipient.toBytes()) === 0 &&
      prev.amountBaseUnits === cur.amountBaseUnits
    ) {
      throw new Error(
        "duplicate (recipient, amount_base_units) reward entry: leaf_index tie-break is " +
          "an unresolved reward-policy.md (M3) decision; supply explicit leafIndex instead",
      );
    }
  }
  return sorted.map((e, i) => ({
    recipient: e.recipient,
    amountBaseUnits: e.amountBaseUnits,
    leafIndex: BigInt(i),
  }));
}

/**
 * Build the reward Merkle root from leaves in `leaf_index` order. Validates §6.6:
 * indices are exactly 0..N-1 (contiguous, no gaps, no duplicates). Empty set ⇒
 * 32 zero bytes (§6.4).
 */
export function rewardRoot(leaves: RewardLeaf[]): Uint8Array {
  const ordered = validateAndOrderLeaves(leaves);
  return merkleRootFromHashes(
    ordered.map((l) => rewardLeafHash(l.recipient, l.amountBaseUnits, l.leafIndex)),
  );
}

/**
 * Build a Merkle inclusion proof for the leaf at `targetLeafIndex` within the
 * reward tree. Returns the proof plus the resolved leaf and root, ready to feed
 * into `claim_reward`.
 */
export function buildRewardProof(
  leaves: RewardLeaf[],
  targetLeafIndex: bigint,
): { leaf: RewardLeaf; proof: ProofStep[]; root: Uint8Array } {
  const ordered = validateAndOrderLeaves(leaves);
  const pos = Number(targetLeafIndex);
  if (pos < 0 || pos >= ordered.length) {
    throw new RangeError(`leaf_index ${targetLeafIndex} out of range [0, ${ordered.length})`);
  }
  const leafHashes = ordered.map((l) => rewardLeafHash(l.recipient, l.amountBaseUnits, l.leafIndex));
  const proof = buildProof(leafHashes, pos);
  return { leaf: ordered[pos], proof, root: merkleRootFromHashes(leafHashes) };
}

/** Sort by leaf_index and enforce the §6.6 contiguity/uniqueness invariants. */
function validateAndOrderLeaves(leaves: RewardLeaf[]): RewardLeaf[] {
  const ordered = leaves.slice().sort((a, b) =>
    a.leafIndex < b.leafIndex ? -1 : a.leafIndex > b.leafIndex ? 1 : 0,
  );
  for (let i = 0; i < ordered.length; i++) {
    if (ordered[i].leafIndex !== BigInt(i)) {
      throw new Error(
        `reward leaf_index must be contiguous 0..N-1 (§6.6); expected ${i}, got ` +
          `${ordered[i].leafIndex} (duplicate or gap)`,
      );
    }
  }
  return ordered;
}

/** Unsigned big-endian byte compare (sol_memcmp order). */
function compareBytes(a: Uint8Array, b: Uint8Array): number {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
}
