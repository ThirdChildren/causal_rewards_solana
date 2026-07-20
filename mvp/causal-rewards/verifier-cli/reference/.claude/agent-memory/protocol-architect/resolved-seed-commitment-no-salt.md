---
name: resolved-seed-commitment-no-salt
description: state-machine.md tx4 reveal_seed reconciled to the ratified salt-free seed commitment (serialization.md §7.2); prose-only, no hash change
metadata:
  type: project
---

`state-machine.md` §2 tx4 (`reveal_seed`) prose was stale: it described a SALTED commitment
`SHA-256(domain‖seed‖salt)` and "stores revealed_seed + salt". The ratified normative authority is
`serialization.md` §7.2: `seed_commitment = SHA-256("CRP-seed-commit-v1" || seed)` — NO salt (a
32-byte high-entropy seed is its own hiding randomness). Fixed tx4 to match: guard now
`SHA-256(SEED_COMMIT_DOMAIN‖seed)`, effect stores `revealed_seed` only, no salt field/arg.

**Why:** verifier-reproducibility-engineer flagged during M2 that a program engineer reading only
state-machine.md could add a salt param and diverge on the commitment (Invariant 2). Spec is frozen
at tag `spec-v1-frozen`; treated as a documentation erratum.

**How to apply:** No salt anywhere in the seed-commitment path. `reveal_seed` takes only the 32-byte
seed and verifies `commit(seed) == frozen seed_commitment`. Erratum was prose-only (state-machine.md
line 37, one line); touched ZERO hashed files (manifest schema/example, evidence example, reward
policy) so `manifest_golden_sha256` (74e0bb82…) and all golden hashes are byte-identical. Same
prose-only-no-hash-change discipline as [[resolved-base58-signer-decode-length]].
