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

- **v1.2 = frozen missingness ONLY, COLLAPSED single-field form (owner-approved 2026-07-30).** Added
  required `design.parameters.missingness_policy ∈ {ineligible, impute_cohort_mean}` to the manifest;
  bumped `spec_version` AND `manifest_version` 1.0.0→1.2.0. Manifest golden moved
  `74e0bb82…`→`ba632e8a…` (CJSON 3852→3886); reward_curve_hash unchanged. **Chose COLLAPSED over the
  migration proposal's original UNION form** (which added a whole `evidence_schedule` object +
  `missingness_action` + equality constraint, golden `ac2b4bdc…`). **Why:** the engine consumes
  exactly one knob — verified `panel.py:200–218` branches on `missingness_policy` alone, no
  coverage-threshold presence-detection path exists; freezing that one field closes the exact
  Invariant-1 hole (engine previously defaulted via `manifest.py:236 params.get(...,"ineligible")`).
  UNION would freeze MORE than "missingness only" and add an unused `expected_cohort_coverage` micro
  field needing a §2.2 scale entry. Rejected the spec_version-only bump variant (golden `b6702e9c…`,
  manifest_version staying 1.0.0) as internally inconsistent — the schema changed, so its version
  changes too. **Cross-impl fan-out is a SEPARATE owner-sequenced task; the spec example is
  intentionally desynced from engine/verifier (still at `74e0bb82…`) until it runs.** Coverage-
  threshold presence-detection (what counts as a *present* cohort-epoch) is a separate future item,
  NOT bundled here. See [[spec-versions]].

- **Benchmark reward curve DECOUPLED from the spec example (owner Condition 3, 2026-07-30).** The M4
  at-scale benchmark reads its own fixture `causal-engine/fixtures/benchmark-manifest.json` carrying
  the recommended shipped-scale + 10%B saturating-cap curve (reward_curve_hash `sha256:eeab732e…`;
  recalibration rejected), NOT `specs/examples/manifest.example.json`
  (which stays frozen under Reading B, curve golden `14b0ec34…` unmoved). **Why:** binding the
  benchmark to the frozen example would either force a spec-golden move on every recalibration or
  publish OLD-curve numbers under a NEW recommendation. Fixture hashes are fixture-scoped (not spec
  goldens). The benchmark REPORT must carry a mandatory curve-provenance line naming the fixture and
  its hash. Contract defined in `v1.2-migration-proposal.md` + `docs/benchmark-plan.md` §7; architect
  defines it, causal-inference-engineer creates + wires `studies.py`.

- **Recommended concentration control = CAP-ONLY as the DEFAULT; recalibration REJECTED (owner
  Condition 2 + Condition-1 study flip, 2026-07-30), guidance not spec.** `multiplicity-recommendation.md`
  §4.0. The Condition-1 compensation study (`docs/compensation-study.md`, commit 4137d7a) REVERSED the
  earlier "calibration + cap together" framing: proportional recalibration (×1/12) UNDER-DEPLOYS — on
  strong-signal `s1` it pays true positives only 6.15%B and recovers 93.85% (the "spending badly by
  spending little" failure). So recalibration is out; keep the shipped curve scale. The per-cohort
  saturation cap is the WHOLE default and the only genuine targeting improver (ratio 0.402→0.245 at
  10%B, the frontier optimum; tighter caps clip true positives). **Finalized numbers (example manifest,
  B=100e9, N=60):** cap_base_units=10,000,000,000 (10% of B); saturating breakpoints
  `[["0","0"],["50000","10000000000"],["100000","10000000000"],["500000","10000000000"],["1000000","10000000000"]]`;
  fixture reward_curve_hash `sha256:eeab732ec6ff4cf09e1185b2b42ad5e5aa83524fefbd6f3d6b079ab43d227ff3`.
  General rule: shipped scale, 10% of B' ceiling. No new frozen field (cap = a saturating
  `reward_curve`); no spec golden moves (Reading B — shipped example curve unchanged at 14b0ec34).
  Cap tunable per experiment.

- **NORMATIVE RULING: no concentration bound / no waste bound (owner, 2026-07-30).** Written in plain
  language into THREE places (not a footnote): `specs/threat-model.md` §4, `docs/integration-guide.md`,
  `docs/benchmark-report.md` limitations. The chain enforces curve SHAPE deterministically but
  guarantees neither a concentration bound (ceiling on one cohort's share) nor a waste bound (ceiling
  on spend to non-additional cohorts), and cannot certify targeting without assuming the truth it is
  forbidden to assume (Invariant 6). Concentration is controllable only at the manifest level (a
  saturating curve); integrators wiring to live incentives must supply their own controls.

See [[spec-versions]] and [[open-questions]].
