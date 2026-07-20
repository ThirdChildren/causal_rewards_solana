---
name: spec-salt-discrepancy
description: state-machine.md still describes a seed-commitment salt that the ratified serialization.md removed; flag to protocol-architect
metadata:
  type: project
---

`state-machine.md §2 transition 4 (reveal_seed)` guard text says the check is
`SHA-256(domain_tag‖seed‖salt) == frozen seed_commitment` and its effect "Stores `revealed_seed` + salt."
But the RATIFIED byte-level authority `serialization.md §7.2` explicitly states **there is no separate salt**:
`seed_commitment = SHA-256(CRP-seed-commit-v1 || seed)` over the raw 32-byte seed.

**Why:** serialization.md is the ratified single source of byte-level truth; the reference impl
(`verifier-cli/reference/assignment.py: seed_commitment`) and the assignment vectors are salt-free and
match it. The state-machine.md wording is stale narrative, not a second construction — but a program
engineer reading only state-machine.md could wrongly add a salt param and diverge on the commitment.

**How to apply:** Always follow serialization.md §7.2 (no salt) for the commitment. The invalid-seed-reveal
adversarial fixture (adv-01) encodes the salt-free construction as the guard. Flag to protocol-architect to
delete the "‖salt" and "+ salt" mentions from state-machine.md tx4 so the two specs agree. Non-blocking for
M2 vectors (the byte spec is unambiguous), but reconcile before M2 program review. Linked: [[vector-catalog]].
