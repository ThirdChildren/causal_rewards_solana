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

Assignment vectors (`test-vectors/assignment/<name>/vector.json`), each showing full chain step1 commitment -> step2 prf -> step3 counts -> step4 leaves(canonical bytes+hash) -> step5 root. This is the M2 CROSS-IMPL oracle: on-chain program + TS SDK + reference MUST reproduce identical roots; any divergence is a bug in the diverging component, never in the vectors (contract stated in test-vectors/README). Roots (stable, backward-compatible — 01–03 unchanged):
- assign-01-bernoulli-p50 — bernoulli 0.5, 4 cohorts. root c229b5cc…, commitment f2261eaa…
- assign-02-fixed-count-2of5 — exactly 2 of 5 treated (prf-ranked, cohort_id tie-break). root 940b42e0…
- assign-03-bernoulli-p25 — bernoulli 0.25, 6 cohorts. root c463b3f1…
- assign-04-bernoulli-p0-allcontrol — boundary ppm=0 → all control. root a29905f9…
- assign-05-bernoulli-p1000000-alltreat — boundary ppm=1e6 → all treatment. root 47a46268…
- assign-06-fixed-count-0of5-allcontrol — boundary k=0. root 75903cbf…
- assign-07-fixed-count-5of5-alltreat — boundary k=n. root d5cd1d84…
- assign-08-bernoulli-single-cohort — n=1, root == sole leaf_hash (Merkle base case). root c6d557cc…
- assign-09-fixed-count-lexical-order — UTF-16 lexical trap (`cohort-10`<`cohort-2`), inputs scrambled to prove order-independence, k=3. root e95324dd…
- assign-10-bernoulli-16cohorts — 16-leaf balanced power-of-2 tree. root a5cb42e9…
- assign-11-fixed-count-3of7 — 7 cohorts (odd) exercises odd-node promotion, k=3. root 5ba5cad7…

Adversarial fixtures (`test-vectors/adversarial/<name>.json`) — negative fixtures with machine-checkable rejection predicate re-run by verify_vectors (a fixture that isn't actually rejectable fails the run). Each has category / invariant / state-machine or §6.5 guard / rejection_code / `check.kind`:
- adv-01-invalid-seed-reveal — SEED_COMMITMENT_MISMATCH (Inv1 freeze-before-reveal; commit(revealed)!=frozen; check computed live via seed_commitment).
- adv-02-duplicate-evidence-epoch — EPOCH_INDEX_NOT_MONOTONIC (state-machine tx5, epoch_index==prev+1).
- adv-03-replayed-evidence-batch — DUPLICATE_EVIDENCE_LEAF (§6.5 strict leaf_hash order; two byte-identical batches → equal leaf_hash → reject; uses specs/examples/evidence.example.json).
- adv-04-stale-evaluation — STALE_EVALUATION_STATE_MISMATCH (tx6/tx8; referenced cohort_root != committed).
- adv-05-evaluation-container-mismatch — CONTAINER_DIGEST_MISMATCH (tx6; echoed analysis_container_digest != frozen).
- adv-06-double-claim — NULLIFIER_ALREADY_USED (tx10; second claim reuses reward-leaf nullifier).

verify_vectors.py additions: adversarial verification + assignment-root-invariant-under-input-order assertion. Still exit 0. Determinism proof: two generate runs → identical aggregate sha256 (725408c9…).

Still owed (M3): estimation vectors, reward-compilation golden roots + their adversarial cases (tampered result, substituted reward root). Linked: [[canonical-rules-proposed]], [[spec-salt-discrepancy]].
