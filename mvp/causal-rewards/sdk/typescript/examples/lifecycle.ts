/**
 * End-to-end lifecycle example for the Causal Rewards Protocol TypeScript SDK.
 *
 * The DETERMINISTIC, off-chain parts run with zero network access (assignment root,
 * seed commitment, reward tree, claim proof) — these are the artifacts an independent
 * verifier reproduces (Invariant 2). The ON-CHAIN section shows how the same values
 * wire into the instruction clients; it only *builds* instructions unless you point it
 * at a running validator (env `ANCHOR_PROVIDER_URL` + `ANCHOR_WALLET`).
 *
 * Run:  npx ts-node examples/lifecycle.ts
 */

import { randomBytes } from "crypto";
import { Keypair, PublicKey } from "@solana/web3.js";

import {
  seedCommitment,
  buildAssignmentRoot,
  assignLeafIndices,
  rewardRoot,
  buildRewardProof,
  verifyProof,
  rewardLeafHash,
  toHex,
} from "../src";

function main(): void {
  const experimentId = "exp-2026-envsensors-demo";

  // ── 1. Freeze-before-reveal (Invariant 1): commit to a seed BEFORE revealing it.
  const seed = new Uint8Array(randomBytes(32));
  const commitment = seedCommitment(seed);
  console.log("experiment_id      :", experimentId);
  console.log("seed (kept secret) :", toHex(seed));
  console.log("seed_commitment    :", toHex(commitment), "  <- goes in the frozen manifest\n");

  // ── 2. After freeze + publish_cohort_root + reveal_seed, derive the assignment.
  //     This root is what publish_cohort_root anchors and the verifier re-derives.
  const cohortIds = ["cohort-0001", "cohort-0002", "cohort-0003", "cohort-0004", "cohort-0005"];
  const { assignments, root: cohortRoot } = buildAssignmentRoot(seed, experimentId, cohortIds, {
    kind: "fixed_count",
    treatmentCount: 2,
  });
  console.log("cohort assignment (fixed_count 2 of 5):");
  for (const a of assignments) console.log(`  ${a.cohortId}  ${a.arm}  prf=${a.prfU64}`);
  console.log("assignment_root    :", toHex(cohortRoot), "\n");

  // ── 3. Reward compiler output → reward tree (§6.6). Recipients are device/cohort
  //     payout addresses; the compiler pins amounts. assignLeafIndices ranks them by
  //     (recipient, amount) into contiguous leaf_index values.
  const recipients = [Keypair.generate().publicKey, Keypair.generate().publicKey, Keypair.generate().publicKey];
  const leaves = assignLeafIndices([
    { recipient: recipients[0], amountBaseUnits: 1_000_000n },
    { recipient: recipients[1], amountBaseUnits: 2_500_000n },
    { recipient: recipients[2], amountBaseUnits: 750_000n },
  ]);
  const rroot = rewardRoot(leaves);
  console.log("reward tree:");
  for (const l of leaves) {
    console.log(`  idx=${l.leafIndex}  ${l.recipient.toBase58()}  amount=${l.amountBaseUnits}`);
  }
  console.log("reward_root        :", toHex(rroot), "  <- locked by finalize_distribution\n");

  // ── 4. Claim-proof construction (matches the on-chain claim_reward verifier).
  const target = leaves[1];
  const { leaf, proof, root } = buildRewardProof(leaves, target.leafIndex);
  const leafH = rewardLeafHash(leaf.recipient, leaf.amountBaseUnits, leaf.leafIndex);
  const ok = verifyProof(leafH, proof, root);
  console.log(`claim proof for leaf_index=${leaf.leafIndex}: ${proof.length} steps, verifies=${ok}`);
  if (!ok || toHex(root) !== toHex(rroot)) throw new Error("claim proof did not verify locally");

  // ── 5. On-chain wiring (build-only unless a provider is configured).
  //     const provider = AnchorProvider.env();
  //     const client = new CausalRewardsClient(provider);
  //     await client.freezeExperiment(experimentId, manifestHash).rpc();
  //     await client.publishCohortRoot({ experimentId, cohortRoot, cohortCount: cohortIds.length,
  //                                      coordinator: provider.wallet.publicKey }).rpc();
  //     await client.revealSeed(experimentId, seed, provider.wallet.publicKey).rpc();
  //     const { builder } = client.buildClaim({ experimentId, leaves, leafIndex: target.leafIndex,
  //                                             recipientToken, vault, expectedRoot: rroot });
  //     await builder.rpc();
  console.log("\nOK — deterministic artifacts reproduced; on-chain wiring shown in comments.");

  // Reference the imports so the example is self-checking for the reader.
  void PublicKey;
}

main();
