# programs/ — Solana on-chain programs (Rust + Anchor)

On-chain layer. Enforces commitments, integrity, settlement. Verifies **process, not truth**.

**Status:** M2 implemented. `anchor build` green; local integration tests (happy +
adversarial) green; IDLs published to `../idl/`. Devnet deploy via
`../scripts/deploy-devnet.sh`.

## Subprograms

- `experiment-registry/` — `ProtocolConfig`, `Experiment`, `CohortSet`. Owns `status`
  and the whole lifecycle up to `Active`. Instructions: `init_protocol_config`,
  `set_paused`, `create_experiment`, `freeze_experiment`, `publish_cohort_root`,
  `reveal_seed`, and CPI-only status transitions (`mark_evaluating`, `mark_challenged`,
  `resolve_upheld`, `resolve_dismissed`, `mark_final`, `mark_closed`).
- `evidence-registry/` — `EvidenceEpoch`. `post_evidence_epoch`. Reads `Experiment`
  (no write). Duplicate/gapped epochs rejected.
- `settlement/` — `Evaluation`, `Distribution`, `ClaimReceipt`. `submit_evaluation`,
  `finalize_distribution`, `claim_reward`, `close_experiment`. Single-use Merkle claims.
- `challenge/` — `Challenge`. `open_challenge`, `resolve_challenge`. Bond escrow +
  finality pause.

`crates/crp-crypto/` is the shared, host-tested hashing / Merkle / seed-commitment
library (byte-identical to `specs/serialization.md` and the verifier reference).

## Cross-program status

`Experiment.status` is written only by experiment-registry. Satellites advance it via
CPI, authenticated by a per-program `[b"cpi_authority"]` PDA verified with Anchor
`seeds::program`. ProtocolConfig stores the three satellite program ids.

## Freeze-before-reveal (Invariant 1, structural)

`Experiment` has no field for a raw seed — only `seed_commitment` (set at create).
`publish_cohort_root` requires `revealed_seed` unset (assignment committed first).
`reveal_seed` recomputes `sha256("CRP-seed-commit-v1"||seed)` and rejects on mismatch
(`SeedCommitmentMismatch`), and only runs in `Active`. No instruction rewrites a frozen
field. Fees are hard-zero; devnet-only guard on `ProtocolConfig`.

## Build / test

See `../scripts/build.sh` (build + IDL), `../scripts/localnet-test.sh` (validator +
deploy + `ts-mocha` + `crp-crypto` vectors), `../scripts/deploy-devnet.sh` (devnet).

## License

Apache-2.0.
