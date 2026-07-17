---
name: vector-catalog
description: Catalog of the golden test vectors written so far (serialization + assignment) and what each exercises; how to regenerate/verify
metadata:
  type: project
---

Golden vectors live in `causal-rewards/test-vectors/`, generated + checked by `causal-rewards/verifier-cli/reference/`.

**Why:** shared fixtures so on-chain, engine, backend, SDKs, simulator all check against the same bytes. Read this before adding vectors to avoid duplicates and keep naming consistent.

**How to apply:** regenerate with `python3 generate_vectors.py`; independently re-derive + assert with `python3 verify_vectors.py` (exit 0 = OK) from the `reference/` dir. Determinism proof: run generate twice, aggregate sha256sum of `test-vectors/**/*.json` is stable.

Serialization vectors (`test-vectors/serialization/`):
- ser-01-key-ordering — object key sort + array order preserved.
- ser-02-unicode-nfc — decomposed input (base+combining) -> precomposed canonical bytes (proves NFC). Built from explicit \u escapes in source so it is encoding-independent.
- ser-03-decimal-scaling — all numerics as strings (no JSON number tokens); scaled fixed-point, negative, zero, big uint, leading-zero string faithfulness.
- ser-04-control-and-escapes — minimal string escaping.
- ser-05-nested-mixed — nesting, bool, null, empty object/array.

Assignment vectors (`test-vectors/assignment/<name>/vector.json`), each showing full chain step1 commitment -> step2 prf -> step3 counts -> step4 leaves(canonical bytes+hash) -> step5 root:
- assign-01-bernoulli-p50 — bernoulli 0.5, 4 cohorts. root c229b5cc..., commitment f2261eaa...
- assign-02-fixed-count-2of5 — exactly 2 of 5 treated (prf-ranked, cohort_id tie-break). root 940b42e0...
- assign-03-bernoulli-p25 — bernoulli 0.25, 6 cohorts, different seed. root c463b3f1...

Still owed (M3): estimation vectors, reward-compilation vectors, and adversarial/failure-case vectors (tampered result, substituted reward root, duplicate/replayed evidence, invalid seed reveal). Linked: [[canonical-rules-proposed]].
