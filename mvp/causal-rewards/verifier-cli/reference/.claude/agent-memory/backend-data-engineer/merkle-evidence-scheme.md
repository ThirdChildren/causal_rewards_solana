---
name: merkle-evidence-scheme
description: Evidence Merkle scheme pinned in specs/serialization.md §6.5 — three trees, 32-byte sort keys, off-chain enforcement rules for M3
metadata:
  type: project
---

Evidence uses three §6.1-shaped SHA-256 Merkle trees (prefixes 0x00 leaf / 0x01 node,
odd-node = promotion not duplication, empty tree = 32 zero bytes). All leaves ordered
**ascending, byte-lexicographic** by a **fixed-width 32-byte** sort key. Chosen over a
semantic (cohort_id, time_range) key to avoid numeric-string comparison ("10" < "9") as a
cross-language footgun; the batch header still binds the semantic fields.

- **Epoch tree** (`DOMAIN_TAG=CRP:evidence:v1`): leaf = `CJSON(full batch object INCLUDING
  batch_signature)`; sort key = `leaf_hash` ascending.
- **Observation sub-commitment** (leaf domain `obs`, root = `observations_commitment.merkle_root_hex`):
  leaf = `SHA256(0x00||'obs'||observation_commitment_be32)`; sort key = the 32 raw bytes
  of `payload_commitment_hex` ascending. Binds only the content commitment, not signer/time_block.
- **Signer-set sub-commitment** (leaf domain `signer`, root = `signer_set_commitment.merkle_root_hex`):
  leaf = `SHA256(0x00||'signer'||signer_pubkey_be32)`; sort key = the 32 raw bytes of the
  base58 `signer_pubkey` ascending.

**Why byte-lexicographic 32-byte:** identical to `sol_memcmp` over 32-byte arrays on-chain and
a plain Python `bytes` sort off-chain; unsigned compare, no endianness/parsing/NFC.

**How to apply (M3 pipeline) — enforce as hard errors:**
- Base58 `signer_pubkey` MUST decode to EXACTLY 32 bytes (schema regex `{32,44}` does NOT
  guarantee this — validate decode length explicitly, else the "fixed-width" premise breaks).
- hex fields (`*_hex`, `merkle_root_hex`) are 64 lowercase hex → exactly 32 bytes.
- Leaf lists MUST be strictly monotonic under the sort key (no duplicates): duplicate signer,
  duplicate content commitment, or byte-identical batch leaf = hard error.
- ed25519 batch signature must be RFC-8032 deterministic; the SIGNED batch (signature bytes
  included) is a pipeline INPUT, not regenerated — golden vectors pin signature bytes so the
  bundle hash reproduces.
- Pipeline recomputes `header_hash_hex` = SHA256(CJSON(batch minus batch_signature)) and verifies
  it matches + verifies signature before accepting.
- Sub-commitment trees are never empty (schema requires signer_count>=1, leaf_count>=1); the
  epoch tree CAN be empty → 32 zero-byte root, which the missingness policy must treat as
  "no batches this epoch".
- Canonical Parquet row order in the audit bundle = the leaf sort order (deterministic). Any
  semantic (cohort/time) index is a secondary off-chain index, never the canonical tree order.

See [[canonical-serialization-notes]] for the CJSON byte rules these leaves ride on.
