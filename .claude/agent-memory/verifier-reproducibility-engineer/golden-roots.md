---
name: golden-roots
description: The ratified golden roots the M3 verifier reproduces and the vector/example each comes from
metadata:
  type: project
---

Roots the verifier reproduces (all from `mvp/causal-rewards/`):
- manifest `74e0bb82…` = SHA-256(CJSON(`specs/examples/manifest.example.json`))
- assignment `c229b5cc…` = assign-01-bernoulli-p50 (`test-vectors/assignment/`)
- evidence epoch `a13e1cdc…` = evidence-01-epoch-multibatch (batch epoch tree)
- evidence signer-set `e45697c8…` = evidence-02, observation-set `1010891b…` = evidence-03
  (sub-trees, reproduced via `_ref.evidence`)
- reward `a9c35cf4…` = reward-01, `ea943182…` = reward-02, `b882c899…` = reward-03

The committed real bundle `verifier-cli/fixtures/bundles/golden-happy/` binds manifest
74e0bb82 + assign-01 + evidence-01 epoch + reward-01, and PASSES every check. reward-02/03 and
evidence-02/03 are reproduced in `tests/test_golden_roots.py` (one bundle can only carry one
reward root / here one epoch). See [[golden-hashes]] (protocol-architect) for the frozen-hash
guardrail: these MUST NOT move without a major/spec_version bump.
