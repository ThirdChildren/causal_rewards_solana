---
name: bundle-seam-contract
description: The ratified M3 audit-bundle seam — which engine file is the on-chain leaf set vs the audit detail, and why the recipient encoding is presentation-only
metadata:
  type: project
---

The M3 audit-bundle seam between causal-engine and evidence-service was RATIFIED in
`causal-rewards/docs/m3-integration-and-spec-round.md` §1 and implemented in the engine.

**The contract (do not silently drift from it):**
- `rewards.parquet` **IS the on-chain leaf set** = settlement source. Columns exactly
  `(leaf_index, recipient_hex, amount_base_units, leaf_hash_hex)`, one row per recipient,
  `leaf_index` ascending contiguous from 0. This is what the reward root commits. Emitted by
  `artifacts.write_rewards`; mirror `rewards.canonical.json` (schema `crp.reward_leaves/v1`).
- `rewards_detail.parquet` = per-(cohort, recipient) Stage-2 split, supplementary auditability
  only. Emitted by `artifacts.write_rewards_detail`; mirror `rewards_detail.canonical.json`
  (schema `crp.rewards_detail/v1`).
- `analysis.json` carries a top-level `evidence_epoch_roots` (ascending epoch order). It is an
  INPUT echoed from the assembler, threaded through `run.analyze(..., evidence_epoch_roots=...)`
  and `crp-engine analyze --evidence-epoch-roots`. The engine never derives it; the assembler
  validates it equals the roots it built.

**Why:** the two sides were designed independently and only broke at the assembly seam. The
orchestrator ratified changing the side that does NOT reproduce goldens.

**How to apply:** the `recipient_hex` (64 lowercase hex) vs `recipient_pubkey` (base58) column
choice is **presentation only and NOT hash-moving** — the §6.6 leaf preimage
(`verifier-cli/reference/reward.py`) consumes 32 RAW bytes; hex/base58 never enters the preimage.
Reward roots reward-01 `a9c35cf4…` / -02 `ea943182…` / -03 `b882c899…` are invariant to it. If a
future change ever couples the on-chain reward-root preimage to the Parquet column dtype, THAT
coupling becomes hash-moving and must move into a v1.2 migration. Engine-side schema doc:
`causal-engine/docs/artifact-schemas.md`. Related: [[multiplicity-study]].
