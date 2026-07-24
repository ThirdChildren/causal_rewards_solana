# Reward Policy

**Spec version:** 1.1.0
**Status:** M1 frozen-READY (awaiting orchestrator freeze gate).
**v1.1.0 (additive, hash-compatible):** closes `serialization.md` §6.6 RESIDUAL A by pinning the
reward **leaf-set shape** to *aggregate-one-leaf-per-recipient* (see "Reward leaf-set shape" under
Stage 2). No frozen manifest field, schema, or golden hash changes — the leaf-set shape is a
compiler/settlement decision, not a manifest field. Tracks `serialization.md` 1.1.0.

The reward policy is a **two-stage** allocation, fully frozen in the manifest at `Frozen`
(`reward_policy` object) and therefore fixed before the seed is revealed and before any outcome is
analyzed (Invariant 1). All arithmetic is integer arithmetic over integer-scaled quantities; no
floats enter any hashed artifact (Invariant 2, `serialization.md`). The total payout can never
exceed the fixed `budget_base_units` (Invariant 3).

- **Stage 1 — cohort valuation.** Each **geo-cohort** (aggregating over its time blocks; the
  estimand unit stays geo-cohort × time-block, see "Stage-1 unit" below) is valued from its
  *conservative* causal effect via the frozen reward curve. This is the only place additionality
  enters payment, and only for designs eligible for the strong causal claim.
- **Stage 2 — intra-cohort split.** A cohort's allocation is divided among its participants by a
  *frozen* quality-weighted rule. This never claims an individual-device counterfactual
  (Invariant 4); it only distributes a cohort-level amount.

Notation: values suffixed `_s` are integers at `positive_improvement_transform.effect_scale`
(the manifest example uses `-6`, i.e. resolution 1e-6). `⌊·⌋` is integer floor division.
`round_he` is round-half-to-even (the single rounding rule, `serialization.md` §1 item 3 / §2.4).

## Stage 1 — cohort valuation

**Stage-1 unit of valuation vs. the estimand unit (normative; resolves the "cohort `c`"
ambiguity).** The frozen *estimand* unit is, and remains, the **geo-cohort × time-block**
(Invariant 4; `manifest.schema.json` `estimand.unit_type = geo_cohort_time_block`). The
Stage-1 *valued* entity `c` is the **geo-cohort**, i.e. one geo-cohort **aggregating over all of
its time blocks** in the analysis set. This is the only reading under which the per-cohort
`analysis_plan.minimum_sample` thresholds are well-defined: `min_time_blocks` counts the geo-cohort's
own time blocks, `min_units_per_cohort` / `min_observations_per_cohort` count over the geo-cohort's
blocks. A single time block is never valued or paid on its own. Equivalently: the estimator
identifies an effect at the geo-cohort × time-block level; Stage 1 then reduces each geo-cohort to
one `(effect_c_s, se_c_s)` pair over its blocks (per the frozen estimator + SE method) and values
that geo-cohort. Throughout this document, "cohort `c`" means this geo-cohort valuation unit.

**Strong-causal-claim eligibility gate (normative; Invariant 3, 6).** A design whose frozen
`design.eligible_for_strong_causal_claim` is `false` (e.g. `observational_replay`) **MUST NOT settle
any positive reward.** For such a design the compiler forces every `conservative_c_s = 0`, hence
every `alloc_c = 0`, produces the empty reward tree (`serialization.md` §6.6, root = 32 zero bytes),
and the entire budget is recoverable — regardless of the point estimates. The analysis container
still runs and emits a **discovery-only** `analysis.json` (effects, SEs, sensitivity, diagnostics for
audit and hypothesis generation), but that artifact carries no settleable allocation. This is
deliberate: paying on a design that cannot support the additionality claim would let the chain
appear to endorse a causal conclusion it cannot ("chain verifies process, not truth", Invariant 6).
Whether a *non-strong-but-not-replay* design may pay is not widened here: only `eligible_for_strong_causal_claim
== true` designs settle positive rewards in v1.1.

For each cohort `c` (the geo-cohort valuation unit defined above; Invariant 4):

**1. Estimate.** The pinned analysis container (`analysis_container_digest`) produces, from the
frozen estimator and SE method, the primary-outcome effect `effect_c_s` and standard error
`se_c_s`, both integer-scaled at `effect_scale`. Cluster-robust SEs per the manifest.

**2. Convert to a non-negative improvement metric.** Apply
`reward_policy.positive_improvement_transform` so that "better" is positive:

```
improvement_c_s = transform(effect_c_s)      # e.g. type "negate_then_clamp" ⇒ -effect_c_s
                                             #      when improvement_direction = "decrease"
se_c_s          = se_c_s                      # SE is invariant under the sign flip
```

**3. Conservative lower bound (Invariant 3).** With
`critical_value = critical_value_micro / 1e6` (one-sided lower; `test_sidedness =
one_sided_lower`):

```
margin_c_s        = round_he(critical_value_micro * se_c_s / 1_000_000)
conservative_c_s  = max(0, improvement_c_s - margin_c_s)
```

This is exactly Invariant 3:
`conservative_effect = max(0, effect - critical_value * standard_error)`, computed on the
improvement metric. A cohort whose lower bound is ≤ 0 gets `conservative_c_s = 0` and therefore
zero allocation (a valid null result, Invariant 8).

**4. Minimum-sample rule (Invariant 3).** A cohort is **eligible** only if it meets *every*
`analysis_plan.minimum_sample` threshold (`min_units_per_cohort`, `min_observations_per_cohort`,
`min_time_blocks`). An ineligible cohort is forced to `conservative_c_s = 0`. If the number of
eligible cohorts is below `min_eligible_cohorts`, the **entire distribution is null**: every
allocation is 0 and the whole budget is recoverable.

**5. Curve valuation.** Map the conservative effect to an absolute cohort allocation ceiling with
the frozen piecewise-linear monotonic curve `reward_policy.reward_curve` (first breakpoint is
`[0, 0]`, so `conservative_c_s = 0 ⇒ alloc_c = 0`). For `conservative_c_s` between breakpoints
`[x0, y0]` and `[x1, y1]`:

```
alloc_c = y0 + round_he( (y1 - y0) * (conservative_c_s - x0) / (x1 - x0) )
```

Below the first / above the last breakpoint, clamp to `y_first` / `y_last`. Monotonic
non-decreasing ⇒ more conservative effect never pays less.

**6. Budget cap / overflow (Invariant 3).** Let `S = Σ_c alloc_c` and `B = budget_base_units`.

```
if S <= B:   budget_c = alloc_c                 # leftover (B - S) is recoverable
else:        budget_c = ⌊ alloc_c * B / S ⌋      # proportional_scale_to_budget, floor
```

Floor division guarantees `Σ_c budget_c ≤ B` in both branches; any floor remainder stays
unallocated and recoverable (`unused_budget_policy = recoverable`). Total is never forced up to
`B` — a weak field of cohorts simply returns budget (Invariant 8).

## Stage 2 — intra-cohort split (frozen quality-weighted)

Within cohort `c` with allocation `budget_c`, each participant `i` who contributed signed,
accepted observations to `c` has an integer weight `w_i` computed from the frozen
`reward_policy.intra_cohort_split.weight_formula`, evaluated over anchored evidence only. The
formula is a fixed expression in the **CRP-WS1 grammar** (below). With `W = Σ_i w_i`:

```
leaf_i = ⌊ budget_c * w_i / W ⌋       if W > 0 and budget_c > 0
leaf_i = 0                            otherwise
```

- Weights derive **only** from evidence-derived, integer-scaled quantities in the audit bundle —
  no off-manifest inputs — so leaves are reproducible (Invariant 2).
- Floor division ⇒ `Σ_i leaf_i ≤ budget_c`; the dust `budget_c − Σ_i leaf_i` is recoverable.
- This distributes a cohort-level amount; it makes no individual-device causal claim
  (Invariant 4).

### Reward leaf-set shape — aggregate-one-leaf-per-recipient (RATIFIED; §6.6 RESIDUAL A closed)

The per-cohort `leaf_i(c)` above is an **intermediate** amount. The on-chain reward leaf set is the
**aggregate over cohorts**: a recipient is identified by the 32-byte ed25519 signer pubkey that
signed its observations (exactly the reward `recipient`), and for each distinct recipient `R` the
compiler emits **one** leaf

```
amount_base_units(R) = Σ_c leaf_i(c)        # sum over every cohort c in which R earned a Stage-2 amount
```

and **omits any recipient whose aggregate sum is 0** (a zero leaf carries no value and would only
waste a `leaf_index` and a `ClaimReceipt` nullifier PDA). Aggregation is integer addition of already-
final, already-floored amounts: it introduces **no further rounding** (`serialization.md` §2.4) and
preserves the budget guarantee exactly —
`Σ_R amount_base_units(R) = Σ_c Σ_i leaf_i(c) ≤ Σ_c budget_c ≤ B`. It is chosen because it (1) makes
`recipient` a **unique key**, giving a total leaf order with no tie-break (`serialization.md` §6.6);
(2) minimizes on-chain footprint — one leaf, one claim, one nullifier per recipient (Invariant 5);
and (3) is a settlement-representation choice fully downstream of the frozen Stage-2 split — it alters
no effect estimate, weight, or split ratio, and makes no individual-device causal claim (Invariant 4,
already satisfied at Stage 1). Per-cohort detail is still recorded in the audit bundle
(`rewards.parquet`) for verification; only the on-chain leaf is aggregated.

Each aggregated leaf becomes a leaf in the reward Merkle tree; the reward root is what
`finalize_distribution` locks, and `claim_reward` proves against. The leaf's byte layout and the
tree's leaf ordering are RATIFIED in `serialization.md` §6.6: the leaf preimage is
`SHA-256( 0x00 || "CRP:reward:v1" || recipient(32) || amount_base_units(u64 BE) || leaf_index(u64 BE) )`,
and leaves are placed by `leaf_index` ascending, contiguous from 0, where `leaf_index` is the 0-based
rank of the aggregate leaf set ordered by `recipient` ascending (unique primary key), then
`amount_base_units` ascending. Because `recipient` is unique after aggregation, **two leaves sharing
a `recipient` is a hard error** (a compiler bug); the SDK's reject-on-ambiguity is the correct
defensive guard. No `leaf_index` tie-break residual remains.

### CRP-WS1 — the frozen weight-formula grammar

`weight_formula` is NOT a free-form expression. It is a **normalized weighted sum over declared
non-negative quality attributes**, in the named grammar **CRP-WS1** (Causal Rewards Weighted-Sum,
version 1). This pins the frozen string's meaning unambiguously now; the formal evaluator ships in
M3, but the semantics below are the contract it must implement.

**Syntax** (matches the `weight_formula` regex in `manifest.schema.json`):

```
weight_formula := term ( " + " term )*
term           := coef "*" attribute
coef           := canonical unsigned integer string   ; serialization.md §2.1, e.g. "1", "1000000"
attribute      := snake_case identifier from the closed vocabulary below
```

- Terms are separated by exactly `" + "` (space-plus-space). The only operators are the implicit
  per-term multiply (`coef * attribute`) and the term-joining `+`. There is **no** division, no
  subtraction, no exponent, and — critically — **no product of two attributes**. A raw
  `accepted_observations * quality_score_micro` is rejected: any nonlinear combination must be
  pre-declared as a single compound attribute (see `quality_adjusted_observations` below) so the
  formula itself stays linear.
- An attribute MAY appear in at most one term. Duplicate attributes are rejected by the evaluator.

**Semantics.** For participant `i`:

```
w_i = Σ_k  coef_k · attribute_k(i)          (integer arithmetic; no rounding)
```

Each `attribute_k(i)` is a **non-negative integer** derived deterministically from that
participant's anchored evidence in the audit bundle. Because `coef_k ≥ 0` and every attribute is
`≥ 0`, `w_i ≥ 0`; the within-cohort normalization `leaf_i = ⌊budget_c · w_i / W⌋` is the
"normalized" step and makes the absolute magnitude (hence `weight_scale`) immaterial to the split
ratio. `weight_scale` is retained only to document the resolution of the attributes for auditors.

**Closed attribute vocabulary (v1).** `weight_formula` may reference ONLY these identifiers. Each is
a non-negative integer per participant, computed by the analysis container from anchored,
signature-verified evidence — never from off-manifest input (Invariant 2, 5):

| Attribute | Meaning | Scale |
| --- | --- | --- |
| `accepted_observations` | count of the participant's signature-verified, accepted observations in cohort `c` | 1 (count) |
| `quality_adjusted_observations` | `accepted_observations · quality_score_micro`, precomputed by the evidence pipeline as one declared attribute (keeps the formula linear) | 1e6 (micro) |
| `uptime_micro` | fraction of the active window the participant reported, micro-scaled | 1e6 (micro) |
| `redundancy_score_micro` | scarcity/redundancy weight of the participant's coverage, micro-scaled | 1e6 (micro) |

Extending the vocabulary is a versioned migration (CRP-WS2, …), never a silent edit.

## Budget guarantee

```
Σ_all leaf_i  ≤  Σ_c budget_c  ≤  B = budget_base_units
```

Both inequalities hold by floor division at each split. Payouts never exceed the fixed budget;
unallocated funds are recovered at `close_experiment`. No redistribution mechanism can push total
payout above `B`.

## Advisory on-chain accounting (security finding M3)

The `Distribution` account records `total_allocated_base_units` at `finalize_distribution`. This
value is an **advisory upper bound only**: the on-chain program enforces `total_allocated_base_units
≤ budget_base_units`, but it does **not** verify that `total_allocated_base_units` equals the sum of
the amounts in the reward Merkle leaves. The chain cannot cheaply recompute `Σ_all leaf_i` — the
leaves live off-chain and are committed only through `reward_root` (`serialization.md` §6.6). A
coordinator could therefore finalize with a `total_allocated_base_units` that overstates (up to the
budget cap) or understates the true leaf sum.

This is deliberate and safe under the trust model (`threat-model.md`), because payout is bounded by
two independent mechanisms that do **not** rely on `total_allocated_base_units`:

- **Per-claim ceiling.** `claim_reward` pays only what a valid Merkle proof against the finalized
  `reward_root` authorizes, once per leaf (single-use nullifier). No claim can pay more than its leaf
  amount, and the budget vault itself caps the aggregate — an over-stated
  `total_allocated_base_units` cannot mint funds.
- **Verifier + challenge.** The verifier CLI recomputes every `leaf_i` and the `reward_root` from
  the audit bundle and the frozen plan. A `reward_root` (or a `total_allocated_base_units` that
  contradicts the recomputed leaves) that does not follow from the bundle is an upheld,
  bond-backed challenge (`state-machine.md` tx7/tx8), which invalidates the evaluation.

`total_allocated_base_units` is thus a convenience/UX figure and a coarse ≤-budget guardrail, never
a cryptographic commitment. The cryptographic commitment to the payout set is `reward_root` alone;
correctness of the split is enforced off-chain by reproduction, consistent with Invariant 6 (the
chain verifies process, not truth).

## Worked example (matches `examples/manifest.example.json`)

Manifest: `effect_scale = -6`, `critical_value_micro = 1_645_000` (1.645, one-sided ~95%),
`improvement_direction = decrease` with transform `negate_then_clamp`, curve breakpoints
`[[0,0],[100000,20e9],[500000,80e9],[1000000,120e9]]`, `budget = 100_000_000_000`.

Three cohorts:

| Cohort | effect (raw) | improvement_s | se_s | margin_s | conservative_s | eligible? | alloc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | −0.30 RMSE | 300000 | 80000 | 131600 | 168400 | yes | 30_260_000_000 |
| B | −0.05 RMSE | 50000 | 60000 | 98700 | 0 | yes | 0 |
| C | −0.40 RMSE | 400000 | 50000 | 82250 | 317750 | **no** (below min sample) | 0 |

- A: `margin = round_he(1_645_000 * 80000 / 1e6) = 131600`; `conservative = 300000 − 131600 =
  168400`; on segment `[100000,20e9]→[500000,80e9]` (slope 150000/unit):
  `alloc = 20e9 + round_he(60e9 * (168400−100000) / 400000) = 20e9 + 10_260_000_000 =
  30_260_000_000`.
- B: lower bound ≤ 0 ⇒ conservative 0 ⇒ alloc 0 (null cohort, pays nothing).
- C: fails minimum-sample ⇒ forced 0 regardless of its strong point estimate.

`S = 30_260_000_000 ≤ B` ⇒ no scaling; `budget_A = 30_260_000_000`; unallocated
`69_740_000_000` recoverable.

Stage 2 for A, two participants. The manifest freezes `weight_formula = "1*quality_adjusted_observations"`
(CRP-WS1). The evidence pipeline precomputes the compound attribute
`quality_adjusted_observations = accepted_observations · quality_score_micro` per participant, and the
weight is the linear term `1 · quality_adjusted_observations`:

- p1: `quality_adjusted_observations = 500 · 900000 = 450_000_000` ⇒ `w = 1 · 450_000_000 = 450_000_000`
- p2: `quality_adjusted_observations = 300 · 800000 = 240_000_000` ⇒ `w = 1 · 240_000_000 = 240_000_000`
- `W = 690_000_000`
- `leaf_p1 = ⌊30_260_000_000 * 450_000_000 / 690_000_000⌋ = 19_734_782_608`
- `leaf_p2 = ⌊30_260_000_000 * 240_000_000 / 690_000_000⌋ = 10_525_217_391`
- `Σ leaves = 30_259_999_999` ⇒ dust `1` base unit recoverable; total ≤ `budget_A ≤ B`. ✓

This example is illustrative of the arithmetic, not a golden vector; deterministic reward-root
vectors are produced by `verifier-reproducibility-engineer` against `serialization.md` once
ratified.
