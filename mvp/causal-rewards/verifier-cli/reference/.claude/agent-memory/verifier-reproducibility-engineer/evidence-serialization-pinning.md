---
name: evidence-serialization-pinning
description: Evidence Merkle tree pinning (serialization.md §6.5), computed CJSON anchor for evidence.example.json, and one open base58-decode determinism advisory
metadata:
  type: project
---

Evidence serialization/Merkle rules as ratified in `specs/serialization.md §6.5` (confirmed
2026-07-20 during the spec-freeze conformance check; specs owned by protocol-architect).

**Three §6.1-shaped Merkle trees, all using node formulas `leaf=SHA256(0x00||DOMAIN||bytes)`,
`node=SHA256(0x01||L||R)`, promotion for odd nodes, 32-zero-byte empty root:**
1. Evidence epoch tree — DOMAIN_TAG `CRP:evidence:v1`; leaf = `CJSON(batch)` (full batch header
   INCLUDING batch_signature); sort key = `leaf_hash` ascending; dup = byte-identical batch = hard error.
2. Observation sub-commitment — leaf domain `obs`; leaf preimage = `0x00||"obs"||obs_commitment_be32`
   (32 raw bytes hex-decoded from `payload_commitment_hex`); sort key = the be32 ascending.
3. Signer-set sub-commitment — leaf domain `signer`; leaf = `0x00||"signer"||signer_pubkey_be32`
   (32 raw bytes base58-decoded from `signer_pubkey`); sort key = the be32 ascending.

**Common ordering rule:** ascending byte-lexicographic (plain unsigned BE bytes) over the tree's
fixed-width 32-byte sort key. No field parsing, no NFC, no numeric-string comparison. Matches
`sol_memcmp` on-chain. Verifier checks strict monotonicity; duplicates are a hard error → total order.

**Computed anchor (regression reference, NOT yet a committed golden vector):**
`specs/examples/evidence.example.json` → CJSON via `verifier-cli/reference/canonical.py` =
1040 bytes, sha256 `901b08d5e9aee2cb9861baed18051a9c9b9feeb444502c64b99163d2e51fa75b`.
Its epoch-tree leaf_hash (single-leaf) = `d15a976874c2503d146d40d347ca6eeab8afe71f6b6d6901d3246e0c242e9a91`.
The example's sub-commitment `merkle_root_hex` values are PLACEHOLDERS — reproducing them needs
companion off-chain observation-leaf / signer-set fixtures I still owe (M3). Example is a
schema+serialization fixture, not a root-reproduction fixture.

**Open advisory I flagged (NON-BLOCKING for the tag):** §6.5 derives `signer_pubkey_be32` by
base58-decoding a variable-length text field but does not explicitly name the base58 variant nor
require decode length == 32 as a hard error. The alphabet is implicitly pinned by the schema regex
`^[1-9A-HJ-NP-Za-km-z]{32,44}$` (Bitcoin/Solana base58) and sorting is on decoded bytes not the
string, so no nondeterminism in practice — but when I build evidence golden vectors I must enforce
`len(decode)==32 else hard error`, and it would be cleaner for protocol-architect to state the
base58 variant + 32-byte length assertion explicitly. See [[evidence-serialization-pinning]].
