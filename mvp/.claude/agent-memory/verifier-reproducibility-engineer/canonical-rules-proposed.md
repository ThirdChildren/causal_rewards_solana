---
name: canonical-rules-proposed
description: The proposed canonical serialization/hashing/Merkle/assignment rules (pre-ratification) and which items still need protocol-architect sign-off
metadata:
  type: project
---

Canonical rules PROPOSED in `causal-rewards/verifier-cli/docs/canonical-serialization.md`, working reference impl in `causal-rewards/verifier-cli/reference/` (Python 3, stdlib only).

**Why:** These rules were defined up front (M1) so programs/SDK/engine/simulator build against them from day one. They are the working definition until `protocol-architect` ratifies them into `specs/serialization.md`.

**How to apply:** Before adding vectors or building the verifier, treat these as the assumed rules; but check whether `specs/serialization.md` exists yet — if it does, the ratified spec wins and any of my proposals it changed must be re-derived.

Rules as proposed:
- Canonical JSON = strict subset of RFC 8785 (JCS): UTF-8 no BOM, no whitespace, object keys sorted by UTF-16 code-unit (compare utf-16-be bytes), arrays order-significant, unique keys after NFC.
- NO JSON number tokens in any hashed artifact. All numerics carried as JSON strings: integers as decimal strings, decimals as integer-scaled fixed-point strings (`*_ppm` = scale 1e6, money in lamports/native int). Reference serializer RAISES on int/float to enforce this mechanically. This is the key lever that eliminates IEEE-754 nondeterminism.
- Strings + keys NFC-normalized before serialize. Minimal escaping (RFC 8785): only `" \ \b \t \n \f \r` and control chars as `\u00xx`; everything else raw UTF-8 (no `/` escape, no `\u` for non-controls).
- Hash = SHA-256 everywhere; raw 32 bytes in trees, lowercase hex for display.
- Merkle: `leaf = SHA-256(0x00 || DOMAIN_TAG || canonical_leaf_bytes)`, `node = SHA-256(0x01 || left || right)`. Per-tree ASCII domain tags: `CRP:participant:v1`, `CRP:assignment:v1`, `CRP:evidence:v1`, `CRP:reward:v1`. Odd node = PROMOTE unchanged (not Bitcoin-duplicate; avoids CVE-2012-2459). Empty root = 32 zero bytes. Leaf order = data-derived canonical sort (assignment: cohort_id asc UTF-16), never insertion order.
- Seed: 32 bytes. `seed_commitment = SHA-256("CRP-seed-commit-v1" || seed)` (frozen in manifest). PRF: `prf_u64 = be_uint64(SHA-256("CRP-assign-v1" || seed || u32be(len exp)||exp || u32be(len cohort)||cohort)[:8])`, length-prefixed to avoid concat collisions. Designs: `bernoulli` (treat iff prf%1_000_000 < treat_fraction_ppm) and `fixed_count` (sort by (prf,cohort_id) asc, first k treated). Assignment leaf = `{"arm":..,"cohort_id":..}` only; prf is an auditable non-leaf intermediate.

**Items flagged [RATIFY] for protocol-architect** (see doc §8 checklist): UTF-16 key order + ASCII-only keys; per-field fixed-point scales + GLOBAL rounding mode (highest divergence risk, needs causal-inference-engineer too); numeric-string regexes; NFC choice; SHA-256 choice; leaf sort keys for participant/evidence/reward; odd-node promotion; empty-root sentinel; seed length/domain tags/PRF framing/design set; whether assignment leaf should bind experiment_id (recommended no).

Next cross-check owed: independently reproduce protocol-architect's provisional manifest golden hash from the canonical-BYTES level (do NOT assume their field layout). Linked: [[vector-catalog]].
