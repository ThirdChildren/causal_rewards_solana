# test-vectors/ — Deterministic golden vectors

Deterministic vectors that every artifact-producing implementation (on-chain
programs, causal engine, backend pipeline, SDKs, simulator) must reproduce
exactly. Governed by the canonical rules in
[`../verifier-cli/docs/canonical-serialization.md`](../verifier-cli/docs/canonical-serialization.md).

Each vector carries: **inputs**, the **expected** bytes/hash/root, and enough
**intermediate** values (canonical bytes, per-leaf hashes) to diff step by step,
plus the spec section it exercises.

## Layout

- `serialization/` — input JSON → canonical UTF-8 bytes → SHA-256.
  - `ser-01-key-ordering` — object key ordering + array order.
  - `ser-02-unicode-nfc` — NFC normalization (decomposed input → precomposed bytes).
  - `ser-03-decimal-scaling` — numeric values as strings (no JSON number tokens);
    scaled fixed-point, negative/zero, big uint.
  - `ser-04-control-and-escapes` — minimal string escaping.
  - `ser-05-nested-mixed` — nesting, booleans, null, empty object/array.
  - `index.json` — name → sha256 summary.
- `assignment/` — seed → cohort assignment → assignment Merkle root. Each case is
  a directory with `vector.json` showing the full chain:
  1. `step1_seed_commitment` — `commitment(seed)` frozen in the manifest
     (freeze-before-reveal: distinct from the reveal/derivation step).
  2. `step2_cohort_prf` — per-cohort PRF from the revealed seed.
  3. `step3_summary` — treatment/control counts.
  4. `step4_leaves` — canonical leaf bytes + per-leaf hash, in canonical order.
  5. `step5_assignment_root` — the assignment Merkle root.
  - `assign-01-bernoulli-p50`, `assign-02-fixed-count-2of5`,
    `assign-03-bernoulli-p25`, plus `index.json`.

## Reproduce / verify

These files are generated and checked by the reference implementation:

```
cd ../verifier-cli/reference
python3 generate_vectors.py   # regenerate
python3 verify_vectors.py      # independently re-derive & assert
```

Estimation and reward-compilation vectors (and adversarial/failure-case vectors)
follow in M3.

## License

Apache-2.0.
