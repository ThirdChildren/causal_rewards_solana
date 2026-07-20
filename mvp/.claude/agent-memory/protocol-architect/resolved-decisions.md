---
name: resolved-decisions
description: Resolved design decisions and their rationale for the Causal Rewards Protocol M1 spec
metadata:
  type: project
---

Design decisions made in the M1 spec draft, with rationale (so future edits don't undo them):

- **Invariants enforced structurally, not just documented.** `estimand.unit_type` is a JSON
  `const` `geo_cohort_time_block` (Invariant 4); `network.cluster` const `devnet` (Invariant 7);
  the manifest schema has NO property to hold the seed, only `assignment.seed_commitment`
  (Invariant 1); `observational_replay` forces `eligible_for_strong_causal_claim=false` via
  `if/then`. **Why:** the task requires structural enforcement; a reader can point to the schema.

- **No floats anywhere hashed.** All decimals are integer-scaled (`*_micro` at 1e-6,
  `effect_scale`/`weight_scale` exponents, curve breakpoints as integer pairs). **Why:**
  Invariant 2 determinism; float formatting is nondeterministic across implementations.

- **critical_value frozen explicitly** (`critical_value_micro`) rather than derived at analysis
  time from confidence level. **Why:** determinism beats re-deriving a quantile; the manifest is
  the pre-analysis plan and must pin every number.

- **Reward = absolute cohort allocation via a piecewise-linear monotonic curve, with
  floor-division splits and proportional_scale_to_budget overflow.** Total payout ≤ budget is
  guaranteed by floor at every split; leftover is `recoverable` (never force-redistributed).
  **Why:** Invariant 3 (conservative) + Invariant 8 (null results valid) + the settlement
  program's unused-budget-recovery instruction. Chose floor (not largest-remainder) for splits to
  keep total strictly ≤ budget and fully deterministic.

- **Rounding split:** one scale-conversion in the conservative bound uses round-half-even (per
  serialization.md §1.3); all budget splits use floor. **Why:** banker's rounding is the single
  mandated rounding rule, but floor on splits is what structurally bounds total ≤ budget.

- **Evidence schema carries commitments/roots/integer counts only** with `additionalProperties:false`
  and no coordinate/telemetry/timestamp-per-reading field; even off-chain observation leaves hold
  only a `payload_commitment`. **Why:** Invariant 5 data minimization, enforced by absence.

- **Evidence schema is now serializer-conformant (2026-07-20).** All 10 numeric evidence fields
  migrated from JSON `integer` to canonical number-STRING form (same regexes as the manifest):
  `epoch_index`, `time_range.start`, `time_range.end`, `signer_count`, `leaf_count`, `accepted_count`,
  `rejected_count`, `distinct_signers`, `quality_score_micro_sum` (micro/1e6), and
  `$defs.observation_leaf.time_block_index`. `end`/`signer_count`/`leaf_count` use `^[1-9][0-9]*$`
  (>=1); the rest use `^(0|[1-9][0-9]*)$`; semantic bounds (start<end, distinct_signers<=signer_count)
  documented per-field + producer/verifier-enforced. Added these fields to `serialization.md` §2.2
  scale table. Example updated (all numerics as strings), still Draft-2020-12 valid, passes
  `canonical.canonical_json_bytes` without raising (1040 CJSON bytes, sha256 901b08d5...). **Why:**
  the ratified serializer RAISES on any int/float token, so evidence records (which become Merkle
  leaves) could not be canonicalized/hashed before this. Closed BEFORE the M1 freeze tag; no evidence
  golden root existed yet so no migration needed. Manifest golden UNCHANGED (74e0bb82..., 3852 bytes).

- **Evidence Merkle leaf sort keys PINNED (serialization.md §6.5), resolving the §6.2 deferral.**
  Three §6.1-shaped trees. (1) Evidence epoch tree, `DOMAIN_TAG CRP:evidence:v1`, leaves = full batch
  headers, `leaf=CJSON(batch incl. batch_signature)`, ordered ascending by 32-byte `leaf_hash`;
  (2) observation sub-commitment (leaf domain `obs`), ordered ascending by the 32-byte content
  commitment; (3) signer-set sub-commitment (leaf domain `signer`), ordered ascending by the 32-byte
  pubkey. All: byte-lexicographic on a fixed-width 32-byte key; duplicates are a hard error (total
  order). **Why:** chose 32-byte-key byte-compare over a semantic (`cohort_id`, `time_range.*`) key to
  avoid numeric-string comparison of integer-string fields (a cross-language footgun) and to make
  on-chain ordering a plain `sol_memcmp` — cheap and identical on-chain and off-chain (Invariant 2).
  No new encoder (leaves are CJSON bytes or raw 32-byte fields). REWARD-tree leaf ordering left
  DEFERRED to M3: reward leaf identity fields (recipient key + single-use claim binding) are
  reward-compiler output not yet specced (reward-policy.md fixes only the amount `leaf_i`).
  Implemented by `backend-data-engineer`, checked by `verifier-reproducibility-engineer`.

- **State machine:** self-loops (`reveal_seed`, `post_evidence_epoch`, `claim_reward`) keep
  `status` but are status-gated; `Evaluating → Final` directly when no challenge; `Challenged`
  only entered when a challenge exists; upheld `resolve_challenge` returns to `Evaluating`.
  **Why:** covers all 11 instructions/8 accounts with no dangling states.

- **Serialization RATIFIED (2026-07-17), adopting the verifier proposal wholesale.** Numbers-as-
  strings (NO JSON number token in any hashed artifact; serializer RAISES on int/float), CJSON =
  RFC 8785 JCS subset (UTF-8, NFC, ASCII-only keys, UTF-16 code-unit key order, minimal escaping),
  SHA-256 sole hash, Merkle leaf=SHA256(0x00||TAG||bytes)/node=SHA256(0x01||L||R) with data-derived
  ordering + odd-node PROMOTION + empty-root = 32 zero bytes, seed commit = SHA256("CRP-seed-commit-v1"
  ||seed) NO SALT, PRF length-prefixed. `serialization.md` §2/§3 are now fully normative; the
  verifier reference is the conformance oracle. **Why:** freeze-blocker; determinism (Invariant 2)
  requires one byte algorithm reproducible cross-language. Golden hashes regenerated (see
  [[spec-versions]]) — bare-integer PROVISIONAL hashes are dead.

- **Whole manifest converted to number-free strings.** Every numeric field in `manifest.schema.json`
  became `type:string` with a canonical-integer regex (unsigned `^(0|[1-9][0-9]*)$`, signed
  `^(0|-?[1-9][0-9]*)$`); JSON Schema numeric min/max bounds are lost and now documented per-field +
  enforced by producer/verifier. **Why:** the ratified serializer cannot hash a manifest containing
  a number token; this is required for the verifier to reproduce the golden hash.

- **Q2 df RESOLVED:** first-class `analysis_plan.df` (unsigned int string), REQUIRED iff
  `critical_value_reference=student_t`, and FORBIDDEN for `normal_approx` (allOf if/then/else with a
  `not:{required:[df]}`). Example stays normal_approx (no df). **Why:** determinism — a student_t
  critical value must be reproducible without recomputing a quantile.

- **Q3 weight_formula RESOLVED — grammar CRP-WS1** (reward-policy.md): a normalized weighted SUM
  `Σ coef_k·attr_k`, syntax `coef*attr` terms joined by ` + `, over a CLOSED attribute vocabulary
  (`accepted_observations`, `quality_adjusted_observations`, `uptime_micro`, `redundancy_score_micro`).
  No attribute×attribute products (nonlinear terms must be pre-declared as one compound attribute,
  e.g. `quality_adjusted_observations`). Enforced by a schema regex on `weight_formula`. Example
  changed from `accepted_observations * quality_score_micro` to `1*quality_adjusted_observations`
  (worked-example numbers unchanged since coef=1 over the precomputed product). Formal evaluator = M3.

- **Q4 switchback/interference RESOLVED:** `design.parameters.interference_assumption` (enum:
  no_interference | partial_interference_within_cohort | spatial_bounded) added; for
  template=switchback, `carryover_blocks` + `washout_blocks` (unsigned int strings) are additionally
  REQUIRED via allOf. Example (cluster_randomized) sets interference_assumption=
  partial_interference_within_cohort. **Why:** Invariant 1 — these belong in the frozen pre-analysis
  plan. Schema description explicitly BANS simulator ground-truth knobs (true_effect, interference
  magnitude, confounding, Sybil params) from design.parameters (Invariant 5/6).

See [[spec-versions]] and [[open-questions]].
