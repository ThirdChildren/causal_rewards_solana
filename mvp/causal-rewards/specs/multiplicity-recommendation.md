# Multiplicity & concentration control — architect recommendation

**Status:** RECOMMENDATION (not yet normative). **The frozen default is UNCHANGED: `none`**
(independent one-sided 5% test per cohort, `reward-policy.md` Stage 1). Adopting this recommendation
as the default is a hash-moving **v1.2 migration** (`specs/v1.2-migration-proposal.md` Item B3) and
requires USER sign-off. Written against the deterministic data in `docs/multiplicity-study.md`
(six scenarios × four regimes).

## The question, framed correctly

The issue is **not** `{none vs Bonferroni}`. Bonferroni (and Šidák) over `m ≈ 30–60` candidate
cohorts drive the per-cohort cut to `α/m ≈ 0.0008`. In the study that collapses power on the
genuine-but-weak scenarios — turning *"most cohorts receive zero/uncertain value"* (our #1
risk-register item) into the **default** outcome. On `s1_strong_signal` FWER pays 2 of 19 payable
true positives (10.5% power) vs BH's 6 (31.6%); on `s5_sybil_contamination` FWER pays 3 of 16 (18.8%)
vs BH's 6 (37.5%). Buying a marginal false-positive reduction at that power cost is the wrong trade
for a budget-allocation problem.

There are **two distinct channels**, and they need **two distinct instruments**:

1. **Discovery channel** — *how many* null cohorts clear the test. A p-value threshold controls this.
2. **Concentration channel** — *how much budget* the survivors absorb. A p-value threshold does
   **not** control this. This is the structural point below.

## Recommendation 1 (threshold): Benjamini–Hochberg FDR at α = 0.05

Adopt **Benjamini–Hochberg (1995) FDR** as the discovery threshold, not an FWER method.

- **Why FDR, not FWER.** We allocate a *budget across many cohorts* and care about the *proportion of
  spend that is wasted*. FDR controls the expected **proportion of paid cohorts that are false** —
  the closest statistical analogue to wasted spend — whereas FWER controls the probability of *any*
  false positive, an unnecessarily strict target that adapts to the *number of tests* rather than the
  *number of true signals present*. In the study BH keeps materially more power than FWER on the
  clear-signal scenarios (`s1`, `s5`) while suppressing pure-null discoveries as hard as FWER does
  on `s2` (all three cut the false-positive **count** 2 → 1).
- **Frozen-manifest compatible.** BH is deterministic given the frozen p-values and the candidate
  family `m` (eligible + identified + causal-design cohorts, fixed by the frozen plan). It reads
  `α` from a frozen field and reproduces bit-for-bit (Invariant 2). No analyst degree of freedom is
  introduced.
- **Where it sits.** Selection runs **before** the reward curve: a cohort BH drops is forced
  `conservative_c_s = 0`, exactly like failing minimum sample (`reward-policy.md` Stage 1 step 4).
  The frozen curve + overflow then re-allocate across survivors.

## The structural point: a threshold mitigates, it does NOT remove, concentration

Under a true null (`s2_null_effect`) the fixed budget does **not** shrink with the number of false
positives — it **concentrates**. `proportional_scale_to_budget` divides the *whole* budget across
whichever cohorts clear the test, so two chance winners split the entire pool, not `2/60` of it.

The study makes the residual explicit and measurable: on `s2`, **BH, Bonferroni and Šidák all cut
the false-positive count 2 → 1, yet the single survivor still absorbs ~26% of the budget** (vs ~30%
under `none`). A p-value threshold bounds the **fraction of PAID cohorts that are null**; it does
**NOT** bound the **fraction of BUDGET** those few nulls receive, because concentration is a
spend-allocation property of the reward *curve + overflow rule*, not of the test. So no threshold
choice — including FDR — closes the waste channel on its own.

## Recommendation 2 (structural): YES, the reward curve must carry part of the fix

**Ruling: the fix cannot live entirely in the p-value threshold; the reward curve must carry the
concentration channel.** I recommend a **conservative-effect floor** as the primary curve-side lever,
with a per-cohort cap as an optional stronger bound.

- **Primary — conservative-effect floor (RECOMMENDED default).** A floor `f_s` on
  `conservative_c_s` below which **no budget deploys**: `alloc_c = 0` for `conservative_c_s < f_s`.
  This directly attacks the concentration channel at its source — a marginal chance-winner that
  clears BH with a *tiny* conservative effect earns **nothing**, so it can never be handed a
  disproportionate share when few cohorts are paid. **No new schema field is required:** the floor is
  expressed as an extra reward-curve breakpoint `["f_s", "0"]` (below `f_s` the piecewise-linear
  curve evaluates to 0). It is hash-moving only through `reward_curve` bytes
  (`specs/v1.2-migration-proposal.md` Item B3).
  - *Tradeoff:* the floor costs power on genuinely small-but-real effects. In the studied scenarios
    this cost is near-zero: `s3_low_power` (effect 0.03) and `s6_demand_shift` (effect 0.05) already
    pay 0 under every regime because the conservative bound swamps them, so a floor set within the
    curve's first paying segment removes essentially no real power while suppressing marginal
    null-driven winners. The floor value is itself a frozen pre-analysis choice (Invariant 1).

- **Optional — per-cohort budget cap (stronger, needs a new field).** A frozen
  `max_cohort_share_micro` cap on any single cohort's `budget_c` (as a micro fraction of `B`) bounds
  concentration *directly* regardless of effect size. It is a hard concentration bound but a blunter
  instrument: it also caps *legitimate* large effects, so it trades away some fidelity of the
  additionality signal. It requires a new `reward_policy.max_cohort_share_micro` field (a further
  hash-moving change). **Recommended as opt-in, not the default** — the floor addresses the
  null-concentration failure mode with less collateral cost.

- **Not recommended: curve concavity as the concentration fix.** Global concavity would compress the
  spread between strong and weak cohorts everywhere, weakening the additionality signal the protocol
  exists to express. The floor is a targeted alternative that leaves the paying region's shape intact.

## Bottom line (recommended package)

**Benjamini–Hochberg FDR (α = 0.05) for the discovery threshold + a conservative-effect floor
(a `["f_s","0"]` curve breakpoint) for the concentration channel.** BH bounds the fraction of paid
cohorts that are null while preserving far more power than FWER (the #1 risk item); the floor bounds
what a marginal survivor can absorb, closing the ~26% single-null residual that no threshold can
touch. Both are deterministic and frozen-manifest compatible. Both are hash-moving and are folded
into `specs/v1.2-migration-proposal.md` Item B3 with computed goldens (floored `reward_curve_hash`
`sha256:0123783e…`; full v1.2 manifest `98490aa3…`). **The default remains `none` until the user
signs off** on the v1.2 migration.

## Data reference

Regenerate the study deterministically: `python -m crp_engine.studies` (see
`docs/multiplicity-study.md`). The `s2_null_effect` headline the recommendation turns on:

| regime | cohorts paid | waste (share of budget) | budget recovered |
| --- | --- | --- | --- |
| none | 2 | 29.61% | 70.39% |
| bonferroni | 1 | 25.94% | 74.06% |
| sidak | 1 | 25.94% | 74.06% |
| benjamini_hochberg | 1 | 25.94% | 74.06% |

The count drops 2 → 1 under every correction; the spend drops only 29.6% → 25.9% — the concentration
residual the curve-side floor exists to close.
