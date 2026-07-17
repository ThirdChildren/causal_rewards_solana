# programs/ — Solana on-chain programs (Rust + Anchor)

On-chain layer. Enforces commitments, integrity, settlement. Verifies **process, not truth**.

## Subprograms

- `experiment-registry/` — frozen manifest hash, funding, status, windows, authorities.
- `evidence-registry/` — batch roots, time ranges, signer commitments, eval artifact hashes.
- `settlement/` — reward root, Merkle claims, expiry, unused-budget recovery.
- `challenge/` — challenge records, bonds, finality pause, resolution.

## State machine

`Draft → Frozen → Active → Evaluating → Challenged → Final → Closed`.
Instructions: `create_experiment`, `freeze_experiment`, `publish_cohort_root`, `reveal_seed`,
`post_evidence_epoch`, `submit_evaluation`, `open_challenge`, `resolve_challenge`,
`finalize_distribution`, `claim_reward`, `close_experiment`.
Accounts: `ProtocolConfig`, `Experiment`, `CohortSet`, `EvidenceEpoch`, `Evaluation`,
`Challenge`, `Distribution`, `ClaimReceipt`.

## Rules

Small audited-shaped instructions. Integration test per critical instruction. Emit public
event per state transition. Multisig authority. No admin path rewrites frozen records or
completed claims. Fees hard-set to zero. Devnet only.

**Status:** stub. Implementation gated on frozen M1 spec (M2).

## License

Apache-2.0.
