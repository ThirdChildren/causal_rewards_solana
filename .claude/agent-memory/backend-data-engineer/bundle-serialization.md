---
name: bundle-serialization
description: Audit-bundle serialization invariants — reward leaf-set column encoding, reward-root preimage invariance, and which frozen goldens actually move
metadata:
  type: project
---

Evidence-service audit bundle (`evidence-service/src/crp_evidence/`). Read before changing any
serialization or golden.

**Reward leaf set (`rewards.parquet`) column = `recipient_hex` (64 lowercase hex).** RATIFIED
seam reconciliation (docs/m3-integration-and-spec-round.md §1.3). `REWARDS_COLUMNS =
(leaf_index, recipient_hex, amount_base_units, leaf_hash_hex)`. `contracts.validate_rewards_table`
enforces `recipient_hex` is 64-hex (decodes to exactly 32 bytes). `bundle._reward_root_from_table`
decodes with `bytes.fromhex`. EVIDENCE `signer_pubkey` stays **base58** (§6.5) — do NOT touch it;
only the REWARD recipient column is hex.

**Why the hex/base58 switch moved no hash:** the §6.6 reward-leaf preimage
(`verifier-cli/reference/reward.py`, the ONE encoder) is
`SHA-256(0x00 ‖ "CRP:reward:v1" ‖ recipient(32 raw bytes) ‖ amount_u64_be ‖ leaf_index_u64_be)`.
Encoding is presentation only; base58 and hex of the same 32 bytes decode identically. Verified:
reward roots byte-identical across both paths. Reward vector goldens stay
a9c35cf4 / ea943182 / b882c899.

**`analysis.json` validator is relaxed to the engine's schema** (top-level
`primary_estimate`/`reward_summary`/`cohorts`, container digest nested under
`engine.analysis_container_digest`), but STILL hard-enforces top-level `evidence_epoch_roots`
equals the epoch roots the assembler built (ascending) — this is the freeze-before-reveal link.
`analysis.json.sha256` = `result_artifact_hash`.

**Which frozen goldens exist and what moves them (important):** the only pinned bundle golden is
`test_frozen_bundle.py`, and it is **evidence-only** (no analysis/rewards). So changing the reward
column name/encoding did NOT move `EXPECTED_BUNDLE_CONTENT_HASH`, `EXPECTED_BUNDLE_LOGICAL_HASH`,
or `EXPECTED_TABLE_CANONICAL_HASHES` (no rewards table in them). The complete-bundle test
(`test_bundle.py::test_complete_bundle_with_analysis_and_rewards`) asserts shape only, no pinned
hash. There is no complete-bundle content-hash golden in `test-vectors/`. Bottom line: a reward-
side column change re-pins nothing here — only add a golden if a complete bundle ever gets pinned.

**Byte-stability knobs:** `EXPECTED_BUNDLE_CONTENT_HASH` is pinned to pyarrow 18.1.0
(`PARQUET_WRITER_SETTINGS`); `bundle_logical_hash` (CJSON over logical rows) is the portable
cross-machine claim. Frozen bundle layout version `1.0.0`, spec version `1.1.0`. Tests run in
`evidence-service/.venv`.
