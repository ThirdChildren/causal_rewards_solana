---
name: determinism-rules
description: Canonical/rounding facts the verifier relies on, and determinism/soundness bugs found while completing the M3 CLI
metadata:
  type: project
---

**Bug found completing M3 (root cause + fix).** `check_result_artifact_and_seam`
reproduced `result_artifact_hash = SHA-256(CJSON(analysis.json))` but NEVER compared it to
the anchored value in `roots.json` — so a cooked analysis.json with an internally consistent
seam PASSED. A tampered-result bundle slipped through. Fixed by comparing the recomputed hash
to `roots["roots"]["result_artifact_hash"]` (and provenance echo) before the seam/container
checks. Lesson: every reproduced value must be compared against the untrusted anchor, not just
recomputed. Added regression: `tests/test_adversarial.py::test_tampered_result_artifact`.

**Strengthening added.** epoch_index monotonicity (EPOCH_INDEX_NOT_MONOTONIC) is now enforced
in `_recompute_epoch_roots` — a re-used/out-of-order epoch_index is a bundle-level reject
(adv-02), not just an on-chain guard.

**Determinism facts (verified, byte-stable across 2 runs):**
- Verifier text + `--json` verdicts are byte-identical run-to-run (no clock, no RNG). JSON via
  `sort_keys=True, separators=(",",":"), ensure_ascii=True`.
- `provenance.json` is EXCLUDED from every bundle hash; the golden fixture pins
  `execution_timestamp="0"` so re-assembly is byte-reproducible.
- Parquet FILE bytes do NOT affect the verdict — the verifier reads only logical string
  columns. So happy-path reproduction is pyarrow-version-independent (only the separate
  `bundle_content_hash` in evidence-service is pyarrow-pinned).

**Evidence tree ordering discriminator (bit me once).** Batch-EPOCH trees sort leaves by
leaf_hash ascending; signer-set / observation SUB-trees sort by the be32 key (pubkey /
commitment), NOT by leaf_hash. So evidence-02/-03 vectors are NOT valid epoch parquets — they
belong inside a batch. The happy bundle uses only evidence-01 (a real batch epoch) as its
epoch; evidence-02/-03 roots are reproduced via `_ref.evidence.signer_subtree /
observation_subtree` in the golden-roots test.
