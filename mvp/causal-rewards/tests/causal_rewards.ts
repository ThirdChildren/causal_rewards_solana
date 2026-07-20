// Integration tests for the Causal Rewards Protocol on-chain programs.
//
// Covers the full happy path (create -> freeze -> publish_cohort_root -> reveal_seed
// -> post_evidence_epoch -> submit_evaluation -> finalize_distribution -> claim_reward
// -> close_experiment) AND the adversarial rejections from the threat model:
// bad seed reveal, double claim, duplicate epoch, mutating a frozen field,
// unauthorized authority, and a challenge blocking finality.

import * as anchor from "@coral-xyz/anchor";
import { BN } from "@coral-xyz/anchor";
import {
  PublicKey,
  Keypair,
  SystemProgram,
  SYSVAR_RENT_PUBKEY,
  LAMPORTS_PER_SOL,
} from "@solana/web3.js";
import {
  TOKEN_PROGRAM_ID,
  createMint,
  getOrCreateAssociatedTokenAccount,
  mintTo,
  getAccount,
} from "@solana/spl-token";
import { assert } from "chai";
import * as h from "./helpers";

const registryIdl = require("../target/idl/experiment_registry.json");
const evidenceIdl = require("../target/idl/evidence_registry.json");
const settlementIdl = require("../target/idl/settlement.json");
const challengeIdl = require("../target/idl/challenge.json");

describe("causal-rewards protocol (M2)", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const conn = provider.connection;
  const wallet = provider.wallet as anchor.Wallet; // acts as coordinator + fee payer

  const registry = new anchor.Program(registryIdl as anchor.Idl, provider);
  const evidence = new anchor.Program(evidenceIdl as anchor.Idl, provider);
  const settlement = new anchor.Program(settlementIdl as anchor.Idl, provider);
  const challenge = new anchor.Program(challengeIdl as anchor.Idl, provider);

  // Actors
  const evaluator = Keypair.generate();
  const m1 = Keypair.generate();
  const m2 = Keypair.generate();
  const m3 = Keypair.generate();
  const p1 = Keypair.generate();
  const p2 = Keypair.generate();
  const challenger = Keypair.generate();

  let mint: PublicKey;
  let coordinatorAta: any;
  const digest = Buffer.alloc(32, 7); // frozen analysis_container_digest
  const seed = Buffer.alloc(32, 0); // revealed seed (32 zero bytes)
  const seedCommit = h.seedCommitment(seed);

  const airdrop = async (pk: PublicKey, sol = 5) => {
    const sig = await conn.requestAirdrop(pk, sol * LAMPORTS_PER_SOL);
    await conn.confirmTransaction(sig, "confirmed");
  };

  const protocolConfig = h.protocolConfigPda();

  before(async () => {
    await airdrop(evaluator.publicKey);
    await airdrop(p1.publicKey);
    await airdrop(p2.publicKey);
    await airdrop(challenger.publicKey);

    mint = await createMint(conn, wallet.payer, wallet.publicKey, null, 0);
    coordinatorAta = await getOrCreateAssociatedTokenAccount(
      conn,
      wallet.payer,
      mint,
      wallet.publicKey
    );
    await mintTo(conn, wallet.payer, mint, coordinatorAta.address, wallet.payer, 100_000_000);
    // fund challenger with tokens for a bond
    const challAta = await getOrCreateAssociatedTokenAccount(
      conn,
      wallet.payer,
      mint,
      challenger.publicKey
    );
    await mintTo(conn, wallet.payer, mint, challAta.address, wallet.payer, 10_000_000);

    // Init protocol config once (idempotent across re-runs on a persistent ledger).
    const cfgInfo = await conn.getAccountInfo(protocolConfig);
    if (!cfgInfo) {
      await registry.methods
        .initProtocolConfig(1, h.EVIDENCE_ID, h.SETTLEMENT_ID, h.CHALLENGE_ID)
        .accounts({
          protocolConfig,
          admin: wallet.publicKey,
          systemProgram: SystemProgram.programId,
        })
        .rpc();
    }
  });

  // Unique per-run suffix so experiments are fresh on a persistent ledger.
  const RUN = Date.now().toString(36);
  const expId = (label: string) => `env-sensors-${label}-${RUN}`;

  const nowSec = () => Math.floor(Date.now() / 1000);

  function windows(overrides: Partial<any> = {}) {
    const now = nowSec();
    return {
      freezeBy: new BN(now + 7200),
      activeStart: new BN(now - 300),
      activeEnd: new BN(now - 60),
      evaluationDeadline: new BN(now + 7200),
      challengeWindowSeconds: new BN(1),
      claimWindowSeconds: new BN(3),
      ...overrides,
    };
  }

  async function createExperiment(
    id: string,
    budget: number,
    win: any = windows(),
    bond = 1_000_000
  ) {
    const idHash = h.experimentIdHash(id);
    const experiment = h.experimentPda(idHash);
    const args = {
      experimentId: id,
      evaluator: evaluator.publicKey,
      authorityThreshold: 2,
      authoritySigners: [m1.publicKey, m2.publicKey, m3.publicKey],
      analysisContainerDigest: [...digest],
      rewardCurveHash: [...Buffer.alloc(32, 0)],
      seedCommitment: [...seedCommit],
      budgetBaseUnits: new BN(budget),
      challengeBondBaseUnits: new BN(bond),
      ...win,
    };
    await registry.methods
      .createExperiment([...idHash], args)
      .accounts({
        protocolConfig,
        experiment,
        vault: h.vaultPda(experiment),
        vaultAuthority: h.vaultAuthorityPda(experiment),
        mint,
        coordinatorFunding: coordinatorAta.address,
        coordinator: wallet.publicKey,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        rent: SYSVAR_RENT_PUBKEY,
      })
      .rpc();
    return { idHash, experiment };
  }

  async function freeze(experiment: PublicKey, signers: Keypair[] = [m1, m2]) {
    await registry.methods
      .freezeExperiment([...Buffer.alloc(32, 9)])
      .accounts({ protocolConfig, experiment })
      .remainingAccounts(
        signers.map((s) => ({ pubkey: s.publicKey, isSigner: true, isWritable: false }))
      )
      .signers(signers)
      .rpc();
  }

  async function publish(experiment: PublicKey, coordinator = wallet.payer) {
    await registry.methods
      .publishCohortRoot([...Buffer.alloc(32, 3)], 4)
      .accounts({
        protocolConfig,
        experiment,
        cohortSet: h.cohortSetPda(experiment),
        coordinator: coordinator.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers(coordinator === wallet.payer ? [] : [coordinator])
      .rpc();
  }

  async function reveal(experiment: PublicKey, s: Buffer = seed) {
    await registry.methods
      .revealSeed([...s])
      .accounts({ protocolConfig, experiment, coordinator: wallet.publicKey })
      .rpc();
  }

  async function postEpoch(experiment: PublicKey, index: number, prev: PublicKey) {
    const exp: any = await registry.account.experiment.fetch(experiment);
    await evidence.methods
      .postEvidenceEpoch(new BN(index), {
        cohortId: "cohort-0001",
        timeStart: exp.activeStart,
        timeEnd: exp.activeEnd,
        signerSetRoot: [...Buffer.alloc(32, 1)],
        observationsRoot: [...Buffer.alloc(32, 2)],
        acceptedCount: new BN(500),
        rejectedCount: new BN(3),
        distinctSigners: new BN(2),
        contentHash: [...Buffer.alloc(32, 4)],
        producer: wallet.publicKey,
      })
      .accounts({
        experiment,
        evidenceEpoch: h.epochPda(experiment, BigInt(index)),
        prevEpoch: prev,
        coordinator: wallet.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .rpc();
  }

  async function submitEval(experiment: PublicKey, rewardRoot: Buffer) {
    await settlement.methods
      .submitEvaluation([...Buffer.alloc(32, 5)], [...rewardRoot], [...digest])
      .accounts({
        protocolConfig,
        experiment,
        evaluation: h.evaluationPda(experiment),
        epochZero: h.epochPda(experiment, 0n),
        cpiAuthority: h.settlementCpiAuthorityPda(),
        evaluator: evaluator.publicKey,
        experimentRegistryProgram: h.REGISTRY_ID,
        systemProgram: SystemProgram.programId,
      })
      .signers([evaluator])
      .rpc();
  }

  async function finalize(experiment: PublicKey, allocated: number, signers = [m1, m2]) {
    await settlement.methods
      .finalizeDistribution(new BN(allocated))
      .accounts({
        protocolConfig,
        experiment,
        evaluation: h.evaluationPda(experiment),
        distribution: h.distributionPda(experiment),
        cpiAuthority: h.settlementCpiAuthorityPda(),
        finalizer: wallet.publicKey,
        experimentRegistryProgram: h.REGISTRY_ID,
        systemProgram: SystemProgram.programId,
      })
      .remainingAccounts(
        signers.map((s) => ({ pubkey: s.publicKey, isSigner: true, isWritable: false }))
      )
      .signers(signers)
      .rpc();
  }

  // ---- Shared state for the happy-path experiment "A" ----
  let expA: PublicKey;
  const budgetA = 1_000_000;
  const leaves = [
    { who: p1, amount: 100_000n, index: 0n },
    { who: p2, amount: 50_000n, index: 1n },
  ];
  let leafHashes: Buffer[];
  let rewardRoot: Buffer;

  it("happy path: create -> freeze -> publish -> reveal", async () => {
    const { experiment } = await createExperiment(expId("a"), budgetA);
    expA = experiment;
    await freeze(expA);
    await publish(expA);
    await reveal(expA);
    const acc: any = await registry.account.experiment.fetch(expA);
    assert.deepEqual(Object.keys(acc.status)[0], "active");
    assert.isTrue(!!acc.revealedSeed);
  });

  it("adversarial: cannot re-publish cohort root (append-only) or freeze again (frozen fields locked)", async () => {
    // Re-publishing would rewrite the assignment commitment — rejected.
    let failed = false;
    try {
      await publish(expA);
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "re-publish must fail");
    // Freeze on a non-Draft experiment is rejected (frozen manifest cannot be re-frozen).
    failed = false;
    try {
      await freeze(expA);
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "re-freeze must fail");
  });

  it("post evidence epochs (monotonic)", async () => {
    await postEpoch(expA, 0, expA); // prev ignored for index 0
    await postEpoch(expA, 1, h.epochPda(expA, 0n));
  });

  it("adversarial: duplicate epoch is rejected", async () => {
    let failed = false;
    try {
      await postEpoch(expA, 0, expA);
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "duplicate epoch must fail");
  });

  it("submit evaluation -> Evaluating, then finalize -> Final", async () => {
    leafHashes = leaves.map((l) => h.rewardLeafHash(l.who.publicKey, l.amount, l.index));
    rewardRoot = h.merkleRootFromHashes(leafHashes);
    await submitEval(expA, rewardRoot);
    let acc: any = await registry.account.experiment.fetch(expA);
    assert.deepEqual(Object.keys(acc.status)[0], "evaluating");

    await h.sleep(1500); // let the challenge window elapse
    await finalize(expA, Number(leaves[0].amount + leaves[1].amount));
    acc = await registry.account.experiment.fetch(expA);
    assert.deepEqual(Object.keys(acc.status)[0], "final");
  });

  it("claim_reward for both participants; single-use enforced", async () => {
    for (const l of leaves) {
      const ata = await getOrCreateAssociatedTokenAccount(
        conn,
        l.who,
        mint,
        l.who.publicKey
      );
      const idx = Number(l.index);
      const proof = h.buildProof(leafHashes, idx).map((s) => ({
        sibling: s.sibling,
        siblingIsLeft: s.siblingIsLeft,
      }));
      await settlement.methods
        .claimReward(new BN(idx), new BN(l.amount.toString()), proof)
        .accounts({
          experiment: expA,
          distribution: h.distributionPda(expA),
          claimReceipt: h.claimReceiptPda(expA, l.index),
          vault: h.vaultPda(expA),
          vaultAuthority: h.vaultAuthorityPda(expA),
          recipientToken: ata.address,
          recipient: l.who.publicKey,
          tokenProgram: TOKEN_PROGRAM_ID,
          systemProgram: SystemProgram.programId,
        })
        .signers([l.who])
        .rpc();
      const bal = await getAccount(conn, ata.address);
      assert.equal(Number(bal.amount), Number(l.amount));
    }
  });

  it("adversarial: double claim of the same leaf is rejected", async () => {
    const l = leaves[0];
    const ata = await getOrCreateAssociatedTokenAccount(conn, l.who, mint, l.who.publicKey);
    const proof = h.buildProof(leafHashes, 0).map((s) => ({
      sibling: s.sibling,
      siblingIsLeft: s.siblingIsLeft,
    }));
    let failed = false;
    try {
      await settlement.methods
        .claimReward(new BN(0), new BN(l.amount.toString()), proof)
        .accounts({
          experiment: expA,
          distribution: h.distributionPda(expA),
          claimReceipt: h.claimReceiptPda(expA, 0n),
          vault: h.vaultPda(expA),
          vaultAuthority: h.vaultAuthorityPda(expA),
          recipientToken: ata.address,
          recipient: l.who.publicKey,
          tokenProgram: TOKEN_PROGRAM_ID,
          systemProgram: SystemProgram.programId,
        })
        .signers([l.who])
        .rpc();
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "double claim must fail (ClaimReceipt nullifier)");
  });

  it("adversarial: forged leaf amount fails Merkle verification", async () => {
    const proof = h.buildProof(leafHashes, 0).map((s) => ({
      sibling: s.sibling,
      siblingIsLeft: s.siblingIsLeft,
    }));
    const ata = await getOrCreateAssociatedTokenAccount(conn, p1, mint, p1.publicKey);
    let failed = false;
    try {
      await settlement.methods
        .claimReward(new BN(5), new BN(999999), proof) // index 5 never existed
        .accounts({
          experiment: expA,
          distribution: h.distributionPda(expA),
          claimReceipt: h.claimReceiptPda(expA, 5n),
          vault: h.vaultPda(expA),
          vaultAuthority: h.vaultAuthorityPda(expA),
          recipientToken: ata.address,
          recipient: p1.publicKey,
          tokenProgram: TOKEN_PROGRAM_ID,
          systemProgram: SystemProgram.programId,
        })
        .signers([p1])
        .rpc();
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "forged claim must fail Merkle verification");
  });

  it("close_experiment recovers unallocated + unclaimed budget", async () => {
    await h.sleep(3200); // let the claim window elapse
    const before = await getAccount(conn, coordinatorAta.address);
    await settlement.methods
      .closeExperiment()
      .accounts({
        protocolConfig,
        experiment: expA,
        distribution: h.distributionPda(expA),
        vault: h.vaultPda(expA),
        vaultAuthority: h.vaultAuthorityPda(expA),
        recoveryToken: coordinatorAta.address,
        cpiAuthority: h.settlementCpiAuthorityPda(),
        cranker: wallet.publicKey,
        experimentRegistryProgram: h.REGISTRY_ID,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .rpc();
    const vaultBal = await getAccount(conn, h.vaultPda(expA));
    assert.equal(Number(vaultBal.amount), 0, "vault emptied");
    const after = await getAccount(conn, coordinatorAta.address);
    // recovered = budget - claimed(150000)
    assert.equal(Number(after.amount - before.amount), budgetA - 150_000);
    const acc: any = await registry.account.experiment.fetch(expA);
    assert.deepEqual(Object.keys(acc.status)[0], "closed");
  });

  // ---------------- Adversarial: seed reveal ----------------
  it("adversarial: reveal_seed with a seed that does not open the commitment is rejected", async () => {
    const { experiment } = await createExperiment(expId("b"), 500_000);
    await freeze(experiment);
    await publish(experiment);
    const wrongSeed = Buffer.alloc(32, 1);
    let failed = false;
    try {
      await reveal(experiment, wrongSeed);
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "wrong seed must be rejected (SeedCommitmentMismatch)");
    // the correct seed still opens it
    await reveal(experiment, seed);
    const acc: any = await registry.account.experiment.fetch(experiment);
    assert.isTrue(!!acc.revealedSeed);
  });

  // ---------------- Adversarial: unauthorized authority ----------------
  it("adversarial: freeze below multisig threshold, and publish by non-coordinator, are rejected", async () => {
    const { experiment } = await createExperiment(expId("c"), 500_000);
    // Only one signer -> threshold (2) not met.
    let failed = false;
    try {
      await freeze(experiment, [m1]);
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "single-signer freeze must fail");
    // Freeze properly, then publish by a non-coordinator signer.
    await freeze(experiment, [m1, m2]);
    failed = false;
    try {
      await publish(experiment, evaluator); // evaluator is not the coordinator
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "non-coordinator publish must fail");
  });

  // ---------------- Challenge blocks finality ----------------
  it("challenge during finality: open_challenge pauses finalize until resolved", async () => {
    const { experiment } = await createExperiment(expId("d"), 500_000);
    await freeze(experiment);
    await publish(experiment);
    await reveal(experiment);
    await postEpoch(experiment, 0, experiment);
    const rr = h.merkleRootFromHashes([
      h.rewardLeafHash(p1.publicKey, 10n, 0n),
    ]);
    await submitEval(experiment, rr);

    // Open a challenge (bond escrowed) -> Challenged.
    const challAta = (
      await getOrCreateAssociatedTokenAccount(conn, challenger, mint, challenger.publicKey)
    ).address;
    const ch = h.challengePda(experiment, challenger.publicKey);
    await challenge.methods
      .openChallenge(1, new BN(1_000_000))
      .accounts({
        protocolConfig,
        experiment,
        challenge: ch,
        bondVault: h.bondVaultPda(ch),
        mint,
        challengerToken: challAta,
        cpiAuthority: h.challengeCpiAuthorityPda(),
        challenger: challenger.publicKey,
        experimentRegistryProgram: h.REGISTRY_ID,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: SystemProgram.programId,
        rent: SYSVAR_RENT_PUBKEY,
      })
      .signers([challenger])
      .rpc();
    let acc: any = await registry.account.experiment.fetch(experiment);
    assert.deepEqual(Object.keys(acc.status)[0], "challenged");

    // Finalize must fail while a challenge is open.
    let failed = false;
    try {
      await finalize(experiment, 10);
    } catch (_) {
      failed = true;
    }
    assert.isTrue(failed, "finalize must be blocked while a challenge is open");

    // Resolve (dismissed): bond forfeited to coordinator; open_challenges -> 0.
    await challenge.methods
      .resolveChallenge(false)
      .accounts({
        protocolConfig,
        experiment,
        challenge: ch,
        bondVault: h.bondVaultPda(ch),
        bondDestination: coordinatorAta.address,
        cpiAuthority: h.challengeCpiAuthorityPda(),
        resolver: wallet.publicKey,
        experimentRegistryProgram: h.REGISTRY_ID,
        tokenProgram: TOKEN_PROGRAM_ID,
      })
      .remainingAccounts([
        { pubkey: m1.publicKey, isSigner: true, isWritable: false },
        { pubkey: m2.publicKey, isSigner: true, isWritable: false },
      ])
      .signers([m1, m2])
      .rpc();

    // Now finalize succeeds (all challenges resolved, none upheld).
    await finalize(experiment, 10);
    acc = await registry.account.experiment.fetch(experiment);
    assert.deepEqual(Object.keys(acc.status)[0], "final");
  });
});
