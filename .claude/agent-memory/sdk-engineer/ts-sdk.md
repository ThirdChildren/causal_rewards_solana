---
name: ts-sdk
description: TypeScript SDK — IDL version targeted, canonical-crypto parity, claim-proof format, error mapping, cross-program PDA/interface agreements
metadata:
  type: project
---

TS SDK lives at `mvp/causal-rewards/sdk/typescript/`. Repo root is `mvp/causal-rewards/`
(NOT `causal-rewards/`). Anchor **0.32.1**, `@solana/web3.js` 1.98.x, IDL/program version **0.1.0**,
serialization spec **v1.0.0**.

**IDL provenance.** The four IDLs are the source of truth at `mvp/causal-rewards/idl/*.json`
(experiment_registry, evidence_registry, settlement, challenge). SDK re-copies them into
`src/idl/*.json`; the `.ts` files are regenerated as `export type <Pascal> = <snake_case JSON literal>`
(Anchor 0.30+ native format). To regen after a program change: copy JSON, rerun the Python snippet
that wraps each JSON as a TS type literal. IDLs are snake_case; Anchor client methods/accounts are
camelCase (`create_experiment` → `program.methods.createExperiment`, `protocol_config` →
`protocolConfig`).

**Canonical crypto parity (the gate).** `src/crypto/` is the single canonical encoding
(serialization.md §6–§7), byte-identical to `crates/crp-crypto` + verifier reference. The M2 gate
test `test/assignment-agreement.test.ts` runs with NO validator and reproduces all 11 golden
assignment roots in `test-vectors/assignment/` (+ each seed commitment, prf_u64, leaf bytes/hash)
and the §6.6 reward-leaf form. **All 11 pass.** Determinism rules that must never regress:
- u64 amount/leaf_index carried as `bigint`, encoded **big-endian** in hashed artifacts (§6.6/§7.3).
- `seed_commitment = SHA-256("CRP-seed-commit-v1" || seed)` — **salt-free** (§7.2).
- assignment leaf order = cohort_id ascending by UTF-16 code unit (JS string `<` compare).
- bernoulli: treat iff `(prf_u64 mod 1_000_000) < treat_fraction_ppm`. fixed_count: sort by
  `(prf_u64, cohort_id)` asc, first k = treatment.
- CJSON forbids bare number/bigint (throws); numbers carried as strings.

**Reward leaf / claim-proof (§6.6).** `reward_leaf_content = recipient(32) || amount_be(8) ||
leaf_index_be(8)` = 48 bytes; `leaf_hash = SHA-256(0x00 || "CRP:reward:v1" || content)`. Leaves
placed at tree position == leaf_index, contiguous 0..N-1 (gap/dup = hard error). `leaf_index`
primary rank: recipient asc (sol_memcmp/BE 32-byte), then amount asc — `assignLeafIndices` REJECTS
duplicate (recipient,amount) since the tie-break is an unresolved reward-policy.md M3 residual.
ClaimProofStep = {sibling:32, siblingIsLeft:bool}; proof folds skip promoted (odd) nodes.
Golden reward-leaf checks embedded in the test (recipient=0, amt=1_000_000, idx=0 →
`773b50b6…c2db299`).

**Endianness split (do not harmonize):** reward leaf preimage = big-endian; ClaimReceipt nullifier
PDA seed `leaf_index` = little-endian (`to_le_bytes`, Solana idiom). pda.ts encodes seeds LE.

**Cross-program PDA agreements (verified against IDL):**
- `vault` seeds `["vault", experiment]` under experiment_registry.
- `vault_authority` seeds `["vault_authority", experiment]` under **settlement** program (it signs
  vault transfers via CPI; registry just stores the address). pda.ts uses SETTLEMENT_PROGRAM_ID.
- experiment PDA seeded by `experiment_id_hash = SHA-256("CRP-exp-id" || id)`.

**Error mapping.** `src/errors.ts` builds tables DIRECTLY from the imported IDL `errors[]` arrays
(no hand-maintained list — a prior hand table had drifted: 6016 was renamed EvaluationInvalidated →
EvaluationNotValid, and abort codes 6023/6024 (registry), 6016/6017 (settlement), 6011 (challenge)
were missing). Re-copying IDLs auto-updates the map. `mapProgramError(program, err)` →
`CausalRewardsError`.

**Instruction/account surface.** `CausalRewardsClient` (src/client.ts) wraps all 4 programs; methods
return Anchor MethodsBuilder (.rpc/.instruction/.transaction/.signers) with PDAs auto-resolved via
`.accountsPartial`. 15 instruction clients incl abort_experiment/refund_bond/mark_aborted +
init_protocol_config. 8 typed account fetchers. `buildClaim` builds proof + guards against a leaf
set that doesn't reproduce the on-chain reward_root before spending a tx.

**Build/test:** `npm test` (gate, no validator), `npm run typecheck`, `npm run build`
(tsconfig.build.json, scoped to src, emits dist/ incl copied idl/*.json). Example
`examples/lifecycle.ts` runs offline via ts-node. No IDL/spec gaps found blocking the SDK.
