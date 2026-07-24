# Modeling notes (causal-engine)

Analysis-time modeling decisions and their justification. **None of these change a committed
byte layout.** The seed→assignment derivations in `specs/serialization.md` §7.4 are RATIFIED and
byte-pinned; everything here is downstream of them, at estimation time.

Where a decision is not yet a frozen manifest field, it is called out explicitly with the
spec-change proposal that would close the gap.

---

## 1. Switchback: carryover / washout — schedule policy (CONFIRMED)

`serialization.md` §7.4 asks `causal-inference-engineer` to confirm the regional-switchback
schedule policy. **Confirmed as specified.** The derivation is:

```
phase(group)      = cohort_prf(seed, experiment_id, group) & 1
arm(group, index) = "treatment" iff ((index + phase(group)) mod 2) == 1
treated_fraction_micro MUST be "500000"
```

### Why this schedule is the right one for this estimand

* **It matches the frozen estimand.** The unit is a geo-cohort × time block and the frozen
  `interference_assumption` is `partial_interference_within_cohort`. A *regional* switchback —
  one randomized phase per geo, deterministic alternation across periods — randomizes at exactly
  the level the interference assumption is stated at. Independent per-period randomization would
  randomize *below* the level of the assumption and buy nothing; a single system-wide schedule
  would randomize *above* it and leave only `T` effective randomization draws for the whole
  network.
* **Balance is structural, not stochastic.** Alternation gives exactly 50% treated periods per
  geo when the period count is even, and ±1 period otherwise. That is why
  `treated_fraction_micro` is pinned to `"500000"`: it is a *description* of the schedule, not an
  input to it. The engine enforces the manifest value (`manifest.py`); the byte derivation
  deliberately does not read it.
* **The randomization unit is the geo, so the geo is the cluster.** With one phase bit per geo,
  the number of independent randomization draws is the number of geos, `G`. The pooled estimator
  therefore clusters on the geo group and reports `G-1` degrees of freedom. Treating each period
  as an independent draw would overstate `G` by the number of periods and understate the SE.

### Carryover / washout policy the engine applies

`carryover_blocks` (`m`) and `washout_blocks` (`w >= m`) are frozen in the manifest and consumed
here, not in the derivation.

* **Rule:** within each **geo group**, ordered by `time_block`, the first `w` blocks after an arm
  switch are DROPPED from the analysis set. The first blocks of a geo are not dropped — at the
  start of the experiment there is no prior treatment to carry over.
* **Why the geo group and not the composite `cohort_id`:** under the §7.4 grammar a composite id
  is `geo|period` and the arm is constant *within* a period, so the switch happens between two
  consecutive composite ids of the same geo. Carryover is a physical property of the geo.
* **Justification.** Bojinov, Simchi-Levi & Zhao (*Design and Analysis of Switchback
  Experiments*, Management Science 2022; arXiv:2009.00148) Assumption 2 (*m-carryover effects*)
  states that `Y_t(w_{1:T})` depends only on `w_{t-m:t}`. Restricting the analysis set to blocks
  whose preceding `m` blocks carried the same arm therefore removes carryover contamination *by
  construction*, with no model for the decay shape. Requiring `w >= m` is exactly that
  restriction; the engine rejects a manifest with `w < m`.
* **The discard set is part of the pre-analysis plan.** `w` is frozen before the reveal, so which
  blocks are dropped cannot be chosen after seeing outcomes (Invariant 1). The engine counts the
  dropped rows in `analysis.json → excluded_records.switchback_washout`.
* **Misspecification is surfaced.** The `carryover_washout_sensitivity` analysis refits at `w` and
  `w+1`. A large shift indicates `m` was frozen too small; that is reported, not corrected.
  (BSZ §4.3–4.4 give the analogous misspecification results and a data-driven procedure for
  identifying `m` across *multiple* experiments — out of scope for one frozen manifest.)

### Standard-error method for `switchback_hac`

The manifest enum allows `standard_error_method ∈ {cluster_robust, hac, matched_pair, classical}`.
For a regional switchback the engine implements `hac` as **unrestricted clustering on the geo
group**. This is deliberate:

* clustering on the geo permits *arbitrary* within-geo serial correlation, which is strictly more
  general than a truncated Bartlett/Newey–West kernel;
* a kernel requires a **bandwidth**, and there is no frozen manifest field to hold one — choosing
  it at analysis time would be an unfrozen analyst degree of freedom (Invariant 1).

An explicit bandwidth *may* be frozen as `design.parameters.hac_bandwidth_blocks`; the engine
reads it if present (see the spec-change proposal below). Absent, the unrestricted cluster form is
used, and `analysis.json` records which was applied.

---

## 2. `matched_cluster`: matching-quality criterion (CONFIRMED)

`serialization.md` §7.4 notes that the *quality* of the matching is a design-validity question,
not a determinism question, and asks for the engine's criterion. **Confirmed: the derivation is
deterministic for any frozen stratification, and the engine does not and must not re-do the
matching.** The stratification is a pre-analysis input committed by `cohort_root` (Invariant 1);
re-matching after the reveal would be exactly the manipulation the freeze exists to prevent.

What the engine does instead:

* **Estimation.** For member `c` of stratum `s`, the block-level difference is
  `d_t = y_{c,t} − mean over the opposite-arm members of s at block t`, signed to read
  treatment-minus-control; the cohort effect is `mean_t d_t` with the paired SE `sd(d)/sqrt(T)`.
  Only members that were *included* earn value — a held-out member contributed no data, so there
  is nothing to pay for.
* **Reported matching-quality criterion (diagnostic, does NOT gate payout):**
  1. **Within-stratum covariate balance.** The standardized mean difference between arms, on every
     frozen covariate plus the exposure-size proxies `n_units` and `n_observations`, with the
     frozen threshold (conventionally |SMD| ≤ 0.1, Austin 2009). Reported per covariate in
     `analysis.json → balance`.
  2. **Stratum completeness.** A stratum with no opposite-arm member yields no contrast; those
     members are reported `identified=false` with the reason
     `no opposite-arm partner in the frozen stratum` and are valued at 0.
  3. **Block overlap.** Fewer than 2 overlapping time blocks between a member and its partners
     makes the paired SE non-estimable; reported and valued at 0.
* **Why it does not gate payout.** The frozen payout gates are exactly two (`reward-policy.md`
  Stage 1 steps 3–4): the minimum-sample rule and a conservative lower bound ≤ 0. Adding a third
  gate after seeing the data would violate Invariant 1. A poor match is grounds for a **challenge**
  and is written into the audit package, not silently netted out of someone's reward.

---

## 3. Per-cohort identification modes (engine decision, data-derived)

`reward-policy.md` Stage 1 needs an `effect_c` and `se_c` **per cohort**. Whether such a thing
exists depends on the *assignment pattern*, not only on the design template. The engine classifies
deterministically and publishes the mode in `analysis.json → identification.per_cohort_mode`:

| Mode | When | Per-cohort contrast | Extra assumption |
| --- | --- | --- | --- |
| `within_cohort` | every cohort has both arms across its own blocks (per-block randomization, switchback) | own treated blocks vs own control blocks | none beyond the frozen interference assumption |
| `matched_stratum` | `matched_cluster` with populated strata | member vs opposite-arm stratum partners, block by block | quality of the frozen matching |
| `between_cohort_vs_control_pool` | arms are constant within a cohort (whole-cohort randomization) | cohort mean vs the randomized control-pool mean | **cohort baselines are exchangeable** — untestable, disclosed |
| `not_identified` | observational replay, or no control units | none | — |

`between_cohort_vs_control_pool` deserves a plain statement, because it is what the current
simulator scenarios produce. Its SE is

```
SE(tau_c) = sqrt( s2_b * (1 + 1/G0) ),      s2_b = unbiased variance of the G0 control-cohort means
```

i.e. it carries the **full between-cohort variance**, because a single cohort's mean is one draw
and its variance is not estimable from that cohort alone. This is deliberately conservative. In a
DePIN panel where cohort-shared noise dominates, it means most cohorts will have a conservative
lower bound of 0. **That is the correct answer about that design's per-cohort power, and the
engine reports it rather than tuning it away** (CLAUDE.md invariant 8). The *pooled* ATE is
unaffected and keeps its full randomization justification.

---

## 4. Cluster-robust inference

* Sandwich per Cameron & Miller (2015, JHR 50(2):317–372) eq. 10–12, with the CR1 correction
  `c = G/(G-1) · (N-1)/(N-K)`.
* **Fixed effects are absorbed by within-demeaning, never entered as dummy columns.** Cameron &
  Miller §III.B: within and LSDV give identical coefficients but different finite-sample
  corrections, and the LSDV one is wrong because it counts the `G-1` dummies in `K`. They name
  `xtreg y x, fe vce(robust)` (the within estimator) as "the desired CRVE". The engine therefore
  demeans and computes `c` with `K` = the number of within-varying regressors.
* Time-block dummies are deliberately **not** added: under randomization they are an efficiency
  nicety, and `T-1` extra columns re-introduce the same `K`-inflation problem.
* `df` is reported as `G-1`, the conventional cluster-robust degrees of freedom, so an auditor can
  check the frozen `critical_value_micro` against the frozen `critical_value_reference`.
* The wild cluster bootstrap (`sensitivity.py`) follows Cameron & Miller §VI.C.2: Rademacher
  two-point weights (Davidson & Flachaire 2008), restricted null, bootstrap-t p-value. It is
  **descriptive** — the frozen critical value, never a bootstrap p-value, governs payout. Note
  Webb (2013): with `G < 10` the two-point p-value is coarse (at most `2^(G-1)` distinct values);
  the engine reports `n_clusters` alongside so the coarseness is visible.

---

## 5. Interference is surfaced, not hidden

* The frozen `interference_assumption` is echoed into `analysis.json → identification.assumptions`
  verbatim. It is an assumption, not a finding.
* The `interference_spillover` sensitivity regresses the outcome on own treatment **plus the
  fraction of treated neighbours in the same block** (requires an adjacency map) and reports the
  spillover coefficient, the spillover-adjusted direct effect, and
  `bias_from_ignoring_spillover = naive − adjusted`.
* When spillover has the same sign as the direct effect, the cohort-level estimand is a **lower
  bound** on the benefit of inclusion, not an unbiased ATE. The note in the artifact says so.
* Guard bands are an *upstream* mitigation: rows excluded by a guard band arrive with
  `eligible=false` and are counted in `excluded_records.upstream_ineligible`, so the exclusion is
  visible in the audit package rather than absorbed silently.

---

## 6. Open spec-change proposals (for `protocol-architect` — engine does NOT act unilaterally)

1. **`missingness_policy` is not a frozen manifest field.** CLAUDE.md requires the missingness
   policy to be frozen *before* analysis. `manifest.schema.json` has no such field. The engine
   reads `design.parameters.missingness_policy ∈ {ineligible, impute_cohort_mean}` and **defaults
   to `ineligible`** (the strictest option). *Proposal:* add it to
   `manifest.schema.json → design.parameters` as a required field with those two enum values.
2. **`hac_bandwidth_blocks` is not a frozen field.** `analysis_plan.standard_error_method` admits
   `hac`, but nothing pins the bandwidth. The engine reads an optional
   `design.parameters.hac_bandwidth_blocks` and otherwise uses unrestricted geo clustering.
   *Proposal:* either add the field, or narrow the enum documentation to state that `hac` for
   `switchback` means "cluster on the geo group".
3. **`eligible_for_strong_causal_claim = false` and settlement.** `reward-policy.md` does not say
   whether a design that is not eligible for the strong causal claim may still settle rewards. The
   engine takes the conservative reading: **it compiles no positive payout** and emits a
   discovery-only `analysis.json`. *Proposal:* state this explicitly in `reward-policy.md` Stage 1.
4. **"cohort `c`" in `reward-policy.md` Stage 1.** The text says "each cohort `c` (a geo-cohort ×
   time-block unit)", but `minimum_sample.min_time_blocks` is a per-cohort threshold, which only
   makes sense if a Stage-1 cohort spans multiple blocks. The engine reads Stage-1 `c` as the
   **geo-cohort**, aggregating over its time blocks, with the *estimand unit* remaining
   geo-cohort × time block. *Proposal:* reword to remove the ambiguity.
5. **No multiplicity control across cohorts.** `critical_value_micro` is applied independently to
   each of `N` cohorts at a one-sided 5% level, so a *true-null* network of 60 cohorts is expected
   to produce ~3 false-positive cohorts and pay them. On simulator scenario `s2_null_effect` the
   engine paid ≈29.6% of the budget to 2 of 60 cohorts under a true zero effect. This is a
   property of the frozen policy, not of the estimator, and the engine will not silently correct
   it. *Proposal:* either freeze a family-wise-adjusted `critical_value_micro` (Bonferroni/Šidák
   over the cohort count, which is known at freeze time), or document the expected false-positive
   spend as an accepted cost of the policy. **Recorded here so it is a disclosed design choice
   rather than a surprise in the benchmark report.**

---

## 7. What the chain does and does not verify

On-chain code enforces commitments, integrity and settlement: the manifest hash, the seed
commitment, the roots, the claim state. **It does not verify that the causal claim is true.** The
claim is only as good as the design, the data and the assumptions listed in
`analysis.json → identification.assumptions`. Every artifact this engine writes repeats that
caveat, and nothing in this repository should be phrased to suggest otherwise (Invariant 6).
