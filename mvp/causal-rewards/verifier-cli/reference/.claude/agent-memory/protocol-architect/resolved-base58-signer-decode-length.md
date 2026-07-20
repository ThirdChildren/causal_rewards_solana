---
name: resolved-base58-signer-decode-length
description: §6.5 signer-set leaf sort key now pins base58 variant + decoded length == 32 (hard error otherwise); prose-only, no bytes/hash changed
metadata:
  type: project
---

Resolved determinism gap in `specs/serialization.md` §6.5 (evidence Merkle leaf sort keys),
signer-set sub-commitment (item 3) — the LAST spec change before the freeze tag.

**Decision:** Added a normative sentence to §6.5 item 3: the base58 variant for `signer_pubkey`
is the Bitcoin/Solana alphabet (already implied by schema regex `^[1-9A-HJ-NP-Za-km-z]{32,44}$`),
and `signer_pubkey` MUST base58-decode to EXACTLY 32 bytes — any other decoded length (e.g. 31/33)
is a hard error and the leaf is rejected. Also referenced this in the item-3 **Sort key** line
("rejected before ordering").

**Why:** The `{32,44}` regex bounds the base58 *character* count, not the *decoded byte* count.
The signer sort key is a fixed-width 32-byte `sol_memcmp` (on-chain) / big-endian byte compare
(off-chain). A non-32-byte decode would diverge on-chain vs off-chain (violates Invariant 2) and
admit an invalid pubkey. Flagged independently by BOTH backend-data-engineer and
verifier-reproducibility-engineer.

**How to apply:** This is a producer/verifier *validation* rule, not a serialization/byte change.
It admits/rejects inputs; it does NOT alter any canonical bytes. It therefore does NOT change
`manifest_golden_sha256` nor the evidence example's CJSON (1040 B, sha256 `901b08d5…`). If asked
to touch the signer leaf again, keep the 32-byte pin.

**Analogous fields confirmed already length-pinned (noted in item 2, left otherwise unchanged):**
the raw-byte-from-hex derivations — `payload_commitment_hex` and both `merkle_root_hex` fields —
are schema-constrained to `^[0-9a-f]{64}$` (64 lowercase hex ≡ exactly 32 bytes), so their decode
is fixed-width by construction and needs no extra pin.

**Scope of edit:** ONLY `specs/serialization.md` was edited (two Edit calls, both in §6.5).
Note: `specs/evidence.schema.json` and `specs/examples/evidence.example.json` also appear modified
in git working tree, but those are OTHER agents' pre-existing in-flight changes, not from this task.
The regex itself (`evidence.schema.json`) was intentionally NOT changed — the rule lives in the
normative prose. See also [[evidence-serialization-pinning]] (verifier agent's memory anchor).
