---
name: golden-hashes
description: The byte-frozen hashed artifacts that must never change without a major/spec_version bump
metadata:
  type: project
---

Frozen golden hashes — MUST stay byte-identical unless doing an explicit major/`spec_version` bump:
- manifest example (`specs/examples/manifest.example.json`): SHA-256 begins `74e0bb82…`
- `reward_curve_hash` (inside manifest): `14b0ec34…`
- evidence example (`specs/examples/evidence.example.json`): `901b08d5…`
- 11 assignment roots (`assign-01…11`, bernoulli + fixed_count) under `test-vectors/assignment/`.

**How to recompute** (from repo root): feed the example through the reference serializer and SHA-256:
`verifier-cli/reference/canonical.py:canonical_json_bytes` then `hashlib.sha256(...).hexdigest()`.
Verified 2026-07-23: manifest → 74e0bb82, evidence → 901b08d5, both match.

Files that must NOT be edited when closing serialization/reward residuals: `manifest.schema.json`,
`evidence.schema.json`, both `examples/*.json`, `manifest.golden.md`. The residuals touch
assignment/reward *derivation* prose and evidence *ordering* prose only — not these bytes.

See [[spec-versions]].
