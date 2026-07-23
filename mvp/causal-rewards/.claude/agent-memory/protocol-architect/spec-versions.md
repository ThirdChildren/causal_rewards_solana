---
name: spec-versions
description: Current version of each spec doc and the two-track (wire/hash contract vs state-machine behavior) versioning model
metadata:
  type: project
---

Spec versioning is **two-track** (defined in `state-machine.md` §5):
- **wire/hash contract version** — governs manifest/evidence schemas, `serialization.md`, all golden hashes.
- **state-machine / protocol-behavior version** — governs `state-machine.md` transition semantics.
They advance independently. `serialization.md` IS wholly the wire/hash contract; its own revision
history is `serialization.md` §9.

Current versions (as of 2026-07-23):
- `serialization.md`: **1.1.0** (wire/hash contract 1.1.0). Additive, hash-compatible.
- `reward-policy.md`: **1.1.0** (tracks serialization 1.1.0; RESIDUAL A).
- `state-machine.md`: behavior **1.1.0**; wire/hash contract reference **1.1.0**.
- manifest `spec_version` field: **"1.0.0"** — MUST NOT change; a v1.0.0 manifest hashes identically
  under wire contract 1.1.

**Migration rule:** a change altering NO byte of any existing hashed artifact = additive minor. A
change altering a golden = major + manifest `spec_version` bump. Never a silent edit — always a
versioned migration with a §9 / §5 revision entry.

See [[golden-hashes]] for the frozen artifacts and [[resolved-residuals-abc]] for what v1.1 pinned.
