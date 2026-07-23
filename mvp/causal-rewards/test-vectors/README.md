# test-vectors/ — Deterministic golden vectors

Deterministic vectors that every artifact-producing implementation (on-chain
programs, causal engine, backend pipeline, SDKs, simulator) must reproduce
exactly. Governed by the canonical rules in
[`../verifier-cli/docs/canonical-serialization.md`](../verifier-cli/docs/canonical-serialization.md).

Each vector carries: **inputs**, the **expected** bytes/hash/root, and enough
**intermediate** values (canonical bytes, per-leaf hashes) to diff step by step,
plus the spec section it exercises.

## Cross-implementation agreement contract (M2)

These vectors are the **independent oracle** for the assignment pipeline. The
contract is:

> Given the same frozen inputs (frozen manifest hash, seed commitment, revealed
> seed, cohort list, design + params), the **on-chain program**, the **TypeScript
> SDK**, and the **reference implementation** MUST each reproduce the *identical*
> per-cohort `prf_u64`, per-leaf canonical bytes + leaf hash, and the final
> **assignment Merkle root**. Any divergence is a bug **in the diverging
> component, never in the vectors** — the vectors are derived solely from the
> ratified spec ([`serialization.md`](../specs/serialization.md)) and its
> reference implementation, with no second encoder.

Because every vector exposes each intermediate (`step2_cohort_prf`,
`step4_leaves[*].leaf_canonical_bytes_hex` / `leaf_hash_hex`,
`step5_assignment_root`), a Rust/Anchor program and a TS client can diff at the
exact step they first disagree, localizing the fault. The positive assignment
roots below are what the M2 gate requires on-chain and in the SDK; the
adversarial fixtures are what "adversarial tests green" means — each MUST be
*rejected* by both the program and the verifier.

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
  - Cases (`index.json` summarizes name → root → seed commitment):
    - `assign-01-bernoulli-p50` — bernoulli 0.5, 4 cohorts.
    - `assign-02-fixed-count-2of5` — exactly 2 of 5 treated (prf-ranked, cohort_id tie-break).
    - `assign-03-bernoulli-p25` — bernoulli 0.25, 6 cohorts, different seed.
    - `assign-04-bernoulli-p0-allcontrol` — boundary `treat_fraction_ppm=0` → all control.
    - `assign-05-bernoulli-p1000000-alltreat` — boundary `treat_fraction_ppm=1000000` → all treatment.
    - `assign-06-fixed-count-0of5-allcontrol` — boundary `treatment_count=0` → all control.
    - `assign-07-fixed-count-5of5-alltreat` — boundary `treatment_count=n` → all treatment.
    - `assign-08-bernoulli-single-cohort` — single-leaf tree: root == leaf_hash (Merkle base case).
    - `assign-09-fixed-count-lexical-order` — UTF-16 lexical ordering (`cohort-10` < `cohort-2`);
      inputs supplied scrambled to prove order-independent derivation.
    - `assign-10-bernoulli-16cohorts` — 16-leaf balanced power-of-2 tree.
    - `assign-11-fixed-count-3of7` — 7 cohorts (odd) exercising odd-node promotion.
    - `assign-12-switchback-2geo-2period` — **switchback** (§7.4): 2 geo × 2 periods;
      per-geo phase bit + parity alternation; `treated_fraction_micro` MUST be `500000`.
    - `assign-13-switchback-3geo-noncontiguous` — switchback with non-contiguous period
      indices (arm is a pure fn of `(group,index)`); odd leaf count (promotion).
    - `assign-14-matched-pairs-2x2` — **matched_cluster** (§7.4) canonical matched pairs:
      two strata `m_s=2`, `frac=500000` → `k_s=round_he(1.0)=1` (one of each pair treated).
    - `assign-15-matched-mixed-strata-halfeven` — matched_cluster mixed strata exercising
      round-half-to-**even** at the exact `.5` tie: `m_s=3, frac=500000` → `k_s=2`; `m_s=2` → `k_s=1`.
    - Switchback/matched vectors add `step2b_switchback_derivation` / `step2b_matched_cluster_derivation`
      (per-group phase / per-stratum `k_s` + ranking). The leaf still carries the FULL composite
      `cohort_id` and leaves sort by the FULL id (§7.5/§6.2) — the `group"|"index` grammar governs
      only how a derivation reads structure out of the id, never the leaf form or ordering.
- `reward/` — reward leaf + reward Merkle root (§6.6, aggregate-one-leaf-per-recipient). Leaf =
  `SHA-256(0x00 || "CRP:reward:v1" || recipient(32) || amount_base_units(u64 BE) || leaf_index(u64 BE))`
  (fixed-width raw bytes, NOT CJSON). Leaves = one per distinct recipient, `amount = Σ` over
  cohorts, **zero-sum recipients OMITTED**; ranked/indexed ascending by `recipient` (BE32, unique
  key) then `amount_base_units`; `leaf_index` = 0-based rank. Each vector shows the input
  contribution list, the aggregate recipient→amount map, dropped zero-sum recipients, the sorted
  leaf table (`leaf_index`, `leaf_content_hex`, `leaf_hash_hex`), and the `reward_root_hex`.
  - `reward-01-multi-recipient-ordering` — multiple recipients, input order ≠ sorted order,
    two recipients each earn across two cohorts (Σ).
  - `reward-02-zero-sum-dropped` — a zero-sum recipient dropped even though its BE32 sorts
    between the two survivors.
  - `reward-03-single-recipient` — single-leaf base case (`reward_root == leaf_hash`).
  - `reward-05-empty-all-zero` — fully-null distribution → empty tree → root = 32 zero bytes (§6.4).
  - `reward-04-duplicate-recipient-error` — HARD ERROR: a leaf set with a duplicate `recipient`
    (compiler bug) is rejected (`DUPLICATE_REWARD_RECIPIENT`).
- `evidence/` — off-chain evidence Merkle roots (§6.5). **Source of truth for the off-chain roots
  only**; the singular on-chain `EvidenceEpoch` account-field mapping is a separate flagged item and
  is not reconciled here. Three §6.1-shaped trees; each vector includes intermediate leaf hashes.
  - `evidence-01-epoch-multibatch` — epoch tree over 3 batch headers; leaf = `CJSON(batch)` (incl.
    `batch_signature`); ordered ascending by `leaf_hash` (input order is not insertion order).
  - `evidence-02-signer-set-multisigner` — signer sub-commitment (domain `signer`); each
    `signer_pubkey` base58-decodes to exactly 32 bytes; sorted ascending by `signer_pubkey_be32`.
  - `evidence-03-observation-set` — observation sub-commitment (domain `obs`); 32-byte content
    commitments sorted ascending, incl. a tight adjacent pair for byte-lexicographic ordering.
  - `evidence-04-empty-tree` — empty-tree sentinel: root = 32 zero bytes for epoch/signer/obs.
  - `evidence-05-signer-not-32-error` — HARD ERROR: a `signer_pubkey` that base58-decodes to a
    non-32-byte value is rejected (`SIGNER_PUBKEY_NOT_32_BYTES`); the `{32,44}`-character schema
    regex does not exclude this, the §6.5 length pin does.
- `adversarial/` — negative fixtures every conforming program **and** the
  verifier MUST reject. Each carries the offending input, `why_rejected`, the
  `invariant` + state-machine/serialization `guard` that forbids it, a stable
  `rejection_code`, and a machine-checkable `check` predicate re-evaluated by
  `verify_vectors.py` (a fixture that fails to be rejectable is itself a bug):
  - `adv-01-invalid-seed-reveal` — revealed seed whose commitment ≠ frozen
    commitment (`SEED_COMMITMENT_MISMATCH`; structural freeze-before-reveal test).
  - `adv-02-duplicate-evidence-epoch` — replayed `epoch_index`
    (`EPOCH_INDEX_NOT_MONOTONIC`).
  - `adv-03-replayed-evidence-batch` — byte-identical batch twice in one epoch
    (`DUPLICATE_EVIDENCE_LEAF`, §6.5 strict leaf order).
  - `adv-04-stale-evaluation` — evaluation referencing a superseded cohort_root
    (`STALE_EVALUATION_STATE_MISMATCH`).
  - `adv-05-evaluation-container-mismatch` — echoed analysis-container digest ≠
    frozen digest (`CONTAINER_DIGEST_MISMATCH`).
  - `adv-06-double-claim` — same reward-leaf nullifier claimed twice
    (`NULLIFIER_ALREADY_USED`).
  - `index.json` — name → category → rejection_code summary.

## Reproduce / verify

These files are generated and checked by the reference implementation:

```
cd ../verifier-cli/reference
python3 generate_vectors.py   # regenerate (byte-stable across runs/machines)
python3 verify_vectors.py      # independently re-derive & assert (exit 0 = OK)
```

`verify_vectors.py` recomputes every canonical byte string, hash, and root from
each vector's declared **inputs** (never trusting the stored expected value),
additionally asserts each assignment root is invariant under input cohort order,
re-derives the switchback phase / matched_cluster `k_s` tables, recompiles every
reward root and off-chain evidence root, and confirms each adversarial + hard-error
fixture's rejection predicate genuinely fires (duplicate reward recipient,
base58-not-32 signer pubkey).

Reference modules (`../verifier-cli/reference/`): `canonical.py`, `merkle.py`,
`assignment.py` (incl. switchback + matched_cluster), `reward.py` (§6.6), and
`evidence.py` (§6.5, dependency-free base58). The generator/verifier are
byte-stable across runs and machines (no wall-clock, no RNG, no float).

## License

Apache-2.0.
