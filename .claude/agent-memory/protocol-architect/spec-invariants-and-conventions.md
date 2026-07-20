---
name: spec-invariants-and-conventions
description: Cross-cutting serialization.md conventions the protocol reuses — endianness, raw-byte vs CJSON leaves, the anti-insertion-order ordering rule, golden hashes not to disturb
metadata:
  type: project
---

Conventions in `specs/serialization.md` (RATIFIED, v1.0.0) that any new hashed-artifact design must
follow:

- **Big-endian everywhere in hashed artifacts.** §7.2 seed, §7.3 PRF (u32be length prefixes, u64
  from BE), and §6.6 reward leaf all use BE. PDA *seeds* (not hashed artifacts) use LE by Solana idiom
  — do not conflate.
- **Two leaf kinds:** CJSON leaves (§3, no JSON number tokens per §2, e.g. assignment §7.5, evidence
  epoch header §6.5) vs raw fixed-width byte leaves (§6.5 obs/signer, §6.6 reward). §2/§3 apply only
  to CJSON leaves.
- **Ordering must be data-derived, never insertion order** (§6.2). Each tree pins a total sort key
  with an explicit tie-break. Reward tree (§6.6) orders by leaf_index, which itself must be a
  data-derived rank.
- **Merkle:** 0x00 leaf / 0x01 node prefixes, per-tree ASCII DOMAIN_TAG, promotion (not duplication)
  on odd nodes (§6.3), empty tree = 32 zero bytes (§6.4). Single hash = SHA-256.

**Golden hashes that MUST stay byte-identical** (never edit manifest/evidence schema or examples
without a versioned migration): manifest golden `74e0bb82...` (`specs/manifest.golden.md`), evidence
example CJSON `901b08d5...`.

**Still-open ordering deferrals in §6.2** (must be pinned before their first golden root): participant
tree (recommendation: participant id ascending, UTF-16 code-unit); switchback/matched-cluster
assignment derivation rules (§7.4, joint with causal-inference-engineer). Reward tree is now resolved
except the one M3 residual — see [[reward-leaf-ratification]].
