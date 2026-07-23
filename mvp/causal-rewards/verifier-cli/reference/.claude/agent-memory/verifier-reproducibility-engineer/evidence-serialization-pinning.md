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

**Advisory RESOLVED (protocol-architect ratified, see [[resolved-base58-signer-decode-length]]):**
§6.5 item 3 now names the base58 variant (Bitcoin/Solana alphabet) and requires `signer_pubkey`
base58-decode to EXACTLY 32 bytes (any other length = hard error, leaf rejected). My reference
`evidence.py::signer_pubkey_be32` enforces this; golden vector `evidence-05-signer-not-32-error`
demonstrates a 33-byte decode is rejected (`SIGNER_PUBKEY_NOT_32_BYTES`).

**Evidence golden vectors LANDED (2026-07-23, v1.1) under `test-vectors/evidence/`** — these are now
the committed off-chain source of truth (roots in [[v1_1-golden-vectors-catalog]]). Built with a
dependency-free base58 in `evidence.py` (stdlib only, matching the reference's no-deps principle).
The example-file `901b08d5…` CJSON anchor still holds as a regression reference. Reminder recorded
in §6.5 and honored in my vectors: do NOT reconcile the multi-batch epoch sub-roots with the
singular on-chain `EvidenceEpoch.signer_set_root`/`observations_root` account fields — that mapping
is a separate flagged item owned by the evidence-registry/state-machine surface.
