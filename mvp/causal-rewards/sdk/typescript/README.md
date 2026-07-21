# @causal-rewards/sdk (TypeScript)

Typed, thin, determinism-safe client for the Causal Rewards Protocol Solana programs:
`experiment-registry`, `evidence-registry`, `settlement`, `challenge`.

The SDK is a **wrapper over the published IDLs** — it does not invent fields or reinterpret
program semantics. The `crypto/` module is the **single canonical encoding**
(`specs/serialization.md`, RATIFIED), byte-for-byte identical to the verifier reference and the
on-chain `crp-crypto` crate. Any client-side hashing / Merkle / assignment derivation goes through
it; there is deliberately no second encoding.

- Targets IDL/program version **0.1.0** (Anchor **0.32.1**, `@solana/web3.js` 1.98.x).
- Serialization spec **v1.0.0**.

## Install

```bash
npm install @causal-rewards/sdk @coral-xyz/anchor @solana/web3.js
```

## What's in the box

- **`CausalRewardsClient`** — one entry point over all four programs. Every instruction method
  resolves the canonical PDAs and returns an Anchor `MethodsBuilder`, so you keep full control
  (`.rpc()`, `.instruction()`, `.transaction()`, `.signers()`).
  Instructions: `initProtocolConfig`, `createExperiment`, `freezeExperiment`, `publishCohortRoot`,
  `revealSeed`, `postEvidenceEpoch`, `submitEvaluation`, `finalizeDistribution`, `claimReward`,
  `openChallenge`, `resolveChallenge`, `closeExperiment`, and the abort path
  `abortExperiment` / `refundBond` / `markAborted`.
- **Account fetchers** — `fetchProtocolConfig`, `fetchExperiment`, `fetchCohortSet`,
  `fetchEvidenceEpoch`, `fetchEvaluation`, `fetchDistribution`, `fetchClaimReceipt`,
  `fetchChallenge` — returning typed shapes (`accounts.ts`).
- **Determinism-safe builders** — `buildAssignmentRoot` (manifest + revealed seed + cohort list →
  root) and `buildClaim` / `buildRewardProof` (Merkle proof + ready `claim_reward` builder).
- **Error mapping** — `mapProgramError(program, err)` turns a raw custom-error code into a readable
  `CausalRewardsError`. Tables are derived directly from the IDLs, so they never drift.

## Determinism guarantees

- `u64` amounts and `leaf_index` are carried as **`bigint`** and encoded **big-endian** in every
  hashed artifact (`serialization.md` §6.6/§7.3). No JS `number`/float ever enters a hashed byte
  string.
- `seed_commitment = SHA-256("CRP-seed-commit-v1" || seed)` — **salt-free** (§7.2), enforcing
  freeze-before-reveal (Invariant 1).
- PDA seeds that carry `leaf_index` use **little-endian** (`to_le_bytes()`, the Solana idiom) — this
  is intentionally different from the big-endian leaf preimage and neither is "harmonized".

The gate test (`test/assignment-agreement.test.ts`) reproduces all 11 golden assignment roots plus
the §6.6 reward-leaf form with **no validator**.

## Quick start

```ts
import { AnchorProvider } from "@coral-xyz/anchor";
import { CausalRewardsClient, seedCommitment } from "@causal-rewards/sdk";

const client = new CausalRewardsClient(AnchorProvider.env());

// Freeze-before-reveal: commit to a seed, freeze, publish the cohort root, then reveal.
const commitment = seedCommitment(seed); // -> goes in the frozen manifest
const { root: cohortRoot } = client.buildAssignmentRoot(seed, experimentId, cohortIds, {
  kind: "fixed_count",
  treatmentCount: 2,
});
await client.publishCohortRoot({ experimentId, cohortRoot, cohortCount: cohortIds.length,
                                 coordinator: wallet.publicKey }).rpc();
await client.revealSeed(experimentId, seed, wallet.publicKey).rpc();

// Claim: build the proof from the full reward-leaf set and send.
const { builder } = client.buildClaim({ experimentId, leaves, leafIndex: 1n,
                                        recipientToken, vault, expectedRoot });
await builder.rpc();
```

See `examples/lifecycle.ts` for a runnable, no-network walkthrough of the deterministic artifacts.

## Develop

```bash
npm install
npm test        # the no-validator agreement gate (11 roots + reward leaf)
npm run typecheck
npm run build   # emits dist/ (tsc)
npm run example # ts-node examples/lifecycle.ts
```
