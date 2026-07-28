# Multiplicity / false-positive study, and the three spend levers (six scenarios x four test regimes x statistical / economic / structural levers)

**Status:** benchmark-report material feeding the `protocol-architect` recommendation (`docs/m3-integration-and-spec-round.md` §2). The frozen default policy is UNCHANGED: `none` (independent one-sided 5% per cohort), and nothing in this document changes a shipped default, a frozen field, or the reward goldens. Everything here is a study-only harness.

**Headline for the spec round.** An FDR level would be a new frozen manifest field and a hash-moving **v1.2 migration**. The two levers this study actually recommends — a per-cohort **cap** and a **curve recalibration** — are *not*: both are reward-curve shapes, and `reward_curve` is already a frozen per-experiment field validated by `reward_curve_hash`. The cap arm is reproduced EXACTLY by a saturating curve compiled through a real manifest (see the verdict, item 4), so it needs no schema change at all.

Regenerate deterministically: `python -m crp_engine.studies` (or `python tools/multiplicity_study.py`). Same committed simulator artifacts + committed seed `0000000000000000000000000000000000000000000000000123456789abcdef` => identical numbers across fresh processes.

## Method

- **Regimes.** `none` = current frozen 5% test (this column is the verbatim engine output, `selected_cohorts=None`). `bonferroni` = `p < alpha/m`. `sidak` = `p < 1-(1-alpha)^(1/m)`. `benjamini_hochberg` = the BH (1995) FDR step-up at level `alpha`. `alpha = 0.05`, one-sided; `m` = candidate cohorts (eligible + identified + causal design).
- **p-values.** `p = P(Z >= improvement_s/se_s)` under the manifest's `critical_value_reference = normal_approx`, consuming the SAME quantized integers as the frozen margin test, so `none` here equals the shipped policy.
- **Selection layer.** A cohort the regime drops is forced `conservative = 0`, exactly like failing minimum sample, so its reward-curve allocation is 0. Surviving cohorts are unaffected: the curve is an ABSOLUTE map `alloc_c = reward_curve(conservative_c)`, so dropping a cohort removes its allocation from the total and the freed budget is **recovered, never redistributed** (see "How the budget is actually allocated" below).
- **Levers.** Beyond the p-value threshold (*statistical*), the study measures a **conservative-effect floor** (*economic*: a cohort below the floor deploys nothing) and a **per-cohort cap** (*structural*: no cohort may draw more than a fixed share of `B`, the clipped excess being recovered, not reassigned). Implementation: `crp_engine.levers` — study-only, integer-only, no frozen default touched.
- **Ground truth.** Homogeneous per scenario from the simulator DGP: all cohorts TRUE-POSITIVE when `true_effect > 0`, all TRUE-NULL when `true_effect == 0`.
- **Power denominator.** The *payable* true-positive cohorts (candidate family `m`), not all cohorts. Control-arm cohorts are held out by design and contribute no data, so counting them would conflate test power with the assignment's treated fraction (~50%). Whole-cohort randomization here uses `between_cohort_vs_control_pool` identification, so only treated cohorts are ever payable.

## Results

| scenario | true_effect | label | regime | m | paid | waste (%B->null) | power (%payable-TP paid) | deployed (%B) | recovered (%B) | max single-cohort share (%B) | scaled_to_budget |
|---|---|---|---|---|---|---|---|---|---|---|---|
| s1_strong_signal | 0.180 | true_positive | none | 19 | 7 | 0.00% | 36.84% | 73.75% | 26.25% | 23.47% | false |
| s1_strong_signal | 0.180 | true_positive | bonferroni | 19 | 2 | 0.00% | 10.53% | 37.85% | 62.15% | 23.47% | false |
| s1_strong_signal | 0.180 | true_positive | sidak | 19 | 2 | 0.00% | 10.53% | 37.85% | 62.15% | 23.47% | false |
| s1_strong_signal | 0.180 | true_positive | benjamini_hochberg | 19 | 6 | 0.00% | 31.58% | 69.22% | 30.78% | 23.47% | false |
| s2_null_effect | 0.000 | true_null | none | 17 | 2 | 29.61% | n/a | 29.61% | 70.39% | 25.94% | false |
| s2_null_effect | 0.000 | true_null | bonferroni | 17 | 1 | 25.94% | n/a | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 0.000 | true_null | sidak | 17 | 1 | 25.94% | n/a | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 0.000 | true_null | benjamini_hochberg | 17 | 1 | 25.94% | n/a | 25.94% | 74.06% | 25.94% | false |
| s3_low_power | 0.030 | true_positive | none | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 0.030 | true_positive | bonferroni | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 0.030 | true_positive | sidak | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 0.030 | true_positive | benjamini_hochberg | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s4_interference | 0.150 | true_positive | none | 22 | 8 | 0.00% | 36.36% | 100.00% | 0.00% | 28.31% | true |
| s4_interference | 0.150 | true_positive | bonferroni | 22 | 3 | 0.00% | 13.64% | 72.50% | 27.50% | 30.15% | false |
| s4_interference | 0.150 | true_positive | sidak | 22 | 3 | 0.00% | 13.64% | 72.50% | 27.50% | 30.15% | false |
| s4_interference | 0.150 | true_positive | benjamini_hochberg | 22 | 6 | 0.00% | 27.27% | 100.00% | 0.00% | 29.71% | true |
| s5_sybil_contamination | 0.150 | true_positive | none | 16 | 10 | 0.00% | 62.50% | 81.93% | 18.07% | 23.23% | false |
| s5_sybil_contamination | 0.150 | true_positive | bonferroni | 16 | 3 | 0.00% | 18.75% | 57.32% | 42.68% | 23.23% | false |
| s5_sybil_contamination | 0.150 | true_positive | sidak | 16 | 3 | 0.00% | 18.75% | 57.32% | 42.68% | 23.23% | false |
| s5_sybil_contamination | 0.150 | true_positive | benjamini_hochberg | 16 | 6 | 0.00% | 37.50% | 76.31% | 23.69% | 23.23% | false |
| s6_demand_shift | 0.050 | true_positive | none | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 0.050 | true_positive | bonferroni | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 0.050 | true_positive | sidak | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 0.050 | true_positive | benjamini_hochberg | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |

### Headline: `s2_null_effect` waste (budget paid under a TRUE ZERO effect)

| regime | cohorts paid | waste (share of budget) | budget recovered | max single-cohort share (%B) | scaled_to_budget |
|---|---|---|---|---|---|
| none | 2 | 29.61% | 70.39% | 25.94% | false |
| bonferroni | 1 | 25.94% | 74.06% | 25.94% | false |
| sidak | 1 | 25.94% | 74.06% | 25.94% | false |
| benjamini_hochberg | 1 | 25.94% | 74.06% | 25.94% | false |

**The two columns that decide the open question.**

- **`max single-cohort share (%B)`** is the concentration channel itself — the largest cheque any one cohort receives, as a share of the fixed budget. Waste and power are aggregate; this is the quantity the "one lucky cohort takes a quarter of the budget" concern is actually about, and no earlier revision of this study reported it, so the channel could not be evaluated at all.
- **`scaled_to_budget`** is the `Stage1Result` flag: `true` iff `sum(alloc) > B` and the downward-only overflow rule fired. It is printed so that the `S <= B` case can never again be misread as normalization. Under the frozen policy it is `true` on `s4_interference` and `false` on `s1_strong_signal`, `s2_null_effect`, `s5_sybil_contamination` — `s2_null_effect` deploys 29.61% and recovers 70.39% while `s4_interference` deploys exactly 100.00%. **Both branches are visible in one table**, which is the direct empirical refutation of the retracted "the budget is divided across whichever cohorts clear the test" claim: if it were divided, `deployed` would read 100% in every row that pays anybody.

## Reading the scenarios

- **`s1_strong_signal` / `s5_sybil_contamination` (clear signal).** BH keeps materially more power than Bonferroni/Šidák while the true-null waste stays 0 (no null cohorts exist). This is the intended regime tradeoff.
- **`s2_null_effect` (the headline, true zero).** With no real signal, every paid cohort is waste. FWER and BH each cut the *count* of false positives from 2 to 1, but the one survivor still absorbs ~26% of the budget — the concentration residual (below).
- **`s3_low_power` (weak, true positive).** The design has essentially no per-cohort power; every regime (incl. `none`) pays nothing and recovers the whole budget. Correct, honest, and NOT something to tune away (CLAUDE.md invariant 8).
- **`s4_interference` (spillover-biased).** Spillover contaminates the between-cohort contrast, so the estimates are biased; the regimes still trade power for false-positive control the same way. Multiplicity control does not fix interference bias — that stays a sensitivity/guard-band problem, surfaced separately.
- **`s6_demand_shift` (confounding).** Its ratified design is `observational_replay` (pays zero regardless); run here in causal mode as a what-if, it *still* pays 0 under every regime — the conservative `between_cohort_vs_control_pool` SE carries the full between-cohort variance and already swamps the confounder, so no false positives even before any multiplicity correction. A clean demonstration that the conservative bound and the multiplicity layer are complementary guards, not substitutes.

## How the budget is actually allocated (absolute scale — NOT normalized)

A previous version of this note claimed the fixed budget is *divided across whichever cohorts clear the test*. **That was wrong**, and the correction matters because it moves the diagnosis from "normalization artifact" to "reward-curve calibration". What `reward_compiler.stage1_valuation` actually does (verified against the code, and against the `recovered (%B)` column above):

```
alloc_c = piecewise_linear(conservative_c, breakpoints)   # ABSOLUTE, per cohort
S       = sum(alloc_c)
budget_c = alloc_c                       if S <= B   # B - S is RECOVERED
budget_c = floor(alloc_c * B / S)        if S >  B   # overflow scales DOWN only
```

There is **no up-normalization anywhere**: no cohort's payout rises because another cohort failed. The `S <= B` branch is the absolute scale of CLAUDE.md (`cohort_reward_pool = value_scale * conservative_effect`); the `S > B` branch is a pro-rata *cap*, and `unused_budget_policy = recoverable` returns the remainder. The structural fix the reader might reach for — "don't deploy budget at all when nothing clears" — **is already the shipped behavior**.

The results table proves it: on `s2_null_effect` (true effect exactly zero) the frozen policy pays 2 of 17 candidate cohorts and deploys only **29.61%** of `B`, recovering **70.39%**. Across the six scenarios the `S > B` scale-down branch fires only on `s4_interference`.

### The real finding: the spend is absolute, and one cohort is enough

Because the scale is absolute, the ~30% is not a share-of-a-pot artifact — it is genuine absolute spend that a *single* cohort can generate. The frozen curve pays 20% of `B` at `conservative = 0.100000` and 80% of `B` at `0.500000`, i.e. about five cohorts at 0.10 exhaust the whole budget. So the gating question is not only "is this cohort significant?" but "is this cohort's effect economically large?", and today **statistical significance does all the gating and economic significance does none.**

| cohort | improvement | SE | margin (1.645*SE) | conservative | one-sided p | alloc (%B) |
|---|---|---|---|---|---|---|
| `cell0007` | 0.242010 | 0.062270 | 0.102434 | 0.139576 | 5.09e-05 | 25.94% |
| `cell0048` | 0.120818 | 0.062270 | 0.102434 | 0.018384 | 2.62e-02 | 3.68% |

**No p-value threshold removes `cell0007`.** Its one-sided p is 5.09e-05, against a Bonferroni cut of `alpha/m = 0.05/17 = 2.94e-03` — it clears the *strictest* correction in the study with room to spare, which is exactly why `bonferroni`, `sidak` and `benjamini_hochberg` all still pay it.

It is not a marginal 1.645-sigma chance winner. The cause is in the design, not the threshold: under whole-cohort `cluster_randomized` assignment a cohort is treated in *every* block, so its cohort-shared noise (simulator ground truth `cluster_noise_sd = 0.08`) is perfectly collinear with its treatment status and can never be differenced out. Each cohort contributes exactly ONE cluster draw. Here that draw landed 3.03 cluster-sigma below baseline, and the control pool's sample SD (0.061257 over G0 = 30 control cohorts) happened to understate the true 0.08 dispersion, inflating the reported z to 3.89.

**And no conservative-effect floor removes it either.** `cell0007`'s conservative effect is 0.139576 — *larger than every paid cohort on the clean-signal scenarios*: `s1_strong_signal` tops out at 0.123141 and `s5_sybil_contamination` at 0.121521. Per-cohort noise (0.08) is the same order as the per-cohort signal these designs are trying to detect, so on this draw the largest "effect" in the whole benchmark is a pure-null artifact. Any floor high enough to reject it rejects the real signal first. That single fact determines the lever comparison below.

## What a p-value regime does and does not bound

- **`none`.** No cross-cohort control. Every cohort with `z >= 1.645` is valued. On `s2` (true zero) this pays some cohorts by construction; the interesting question is how much budget that costs, not how many cohorts it is.
- **Bonferroni / Šidák (FWER).** Per-cohort cut ~`alpha/m`. They bound the probability of *any* false discovery. Bonferroni ⊂ Šidák (Šidák's cut is marginally larger, hence weakly more power); under independence Šidák is exact and Bonferroni conservative.
- **Benjamini–Hochberg (FDR).** Bounds the expected *proportion of paid cohorts* that are false. It keeps materially more power than FWER when true signals are present, which is why it is the statistical candidate.

**The measured limit of every regime here: they bound a COUNT, and the exposure is a SPEND.** On `s2` BH cuts the false-positive count 2 -> 1, but the budget paid to true nulls falls only 29.61% -> 25.94%, because the survivor is the *large* one. The largest single-cohort share is 25.94% under `none` and **still 25.94% under BH** — the correction does not touch the concentration channel at all, it only removes the small payer.

This is not a subtlety about FDR. It is arithmetic: `cell0007` alone accounts for 25.94% of `B`, and no correction in the study removes it (its one-sided p is 5.09e-05). Any lever that is going to change the exposure has to act on the *size* of a single cohort's cheque, which is the reward curve — not on the p-value.

## Lever comparison: statistical (BH) vs economic (floor) vs structural (cap) vs calibration (C-R)

All arms run on the SAME compiler: absolute scale, unused budget recovered. Arm 1 is the verbatim frozen engine output and is byte-identical to the `none` regime row above; arm 2 is identical to the `benjamini_hochberg` row (both asserted in `tests/test_levers.py`). `floor` is in `effect_scale` units (`-6`); `cap` is the maximum share of `B` a single cohort may draw, with the clipped excess recovered. Note that the per-cohort one-sided 5% test is ALWAYS in force — the "no correction" arms drop only the *cross-cohort* correction.

**Arm 6 (C-R curve recalibration)** rescales the benchmark reward curve to the *equal-share calibration*: choose the scale so that a network in which all `N` declared cohorts deliver the curve's own reference effect (`0.100000`, its first paying breakpoint) exactly exhausts `B`. Formally `N * curve(x_ref) = B`, i.e. `scale = B / (N * curve_0(x_ref))`. Both inputs (`cohort_count` and the curve) are frozen pre-analysis, so this is a pre-registration choice, not a post-hoc fit. Arm 6 is run through a genuinely recompiled manifest — new breakpoints, recomputed `reward_curve_hash`, full Stage-1/Stage-2/leaf path — not simulated arithmetic.

| scenario | declared `cohort_count` N | frozen `curve(x_ref)` (%B) | equal share 1/N (%B) | calibrated scale | on the swept grid? |
|---|---|---|---|---|---|
| s1_strong_signal | 60 | 20.00% | 1.67% | x1/12 | yes |
| s2_null_effect | 60 | 20.00% | 1.67% | x1/12 | yes |
| s3_low_power | 20 | 20.00% | 5.00% | x1/4 | yes |
| s4_interference | 60 | 20.00% | 1.67% | x1/12 | yes |
| s5_sybil_contamination | 60 | 20.00% | 1.67% | x1/12 | yes |
| s6_demand_shift | 60 | 20.00% | 1.67% | x1/12 | yes |

That is the calibration defect, quantified: the frozen curve hands its first paying breakpoint an allocation an order of magnitude larger than an equal share of the budget across the cohorts the experiment declared. `x1/2` is swept alongside so the grid brackets the calibrated point from above.

**Arm 6b** is the same recalibration idea applied to the curve's *shape* instead of its scale: saturate the curve at a ceiling. It is reported because it answers a spec question, not a statistical one — see the verdict.

- **waste** = share of `B` paid to true-null cohorts. **legit** = share of `B` reaching true-positive cohorts. **power** = share of *payable* true-positive cohorts that are paid anything (a head-count, so it is insensitive to the cap and to any proportional recalibration by construction; their cost shows up in **legit**, not in power). **max share** = the concentration channel. **scaled** = the `S > B` overflow flag.

| scenario | arm | param | paid | waste (%B) | power (%payable-TP) | legit (%B) | deployed (%B) | recovered (%B) | max single-cohort share (%B) | scaled_to_budget |
|---|---|---|---|---|---|---|---|---|---|---|
| s1_strong_signal | 1. no correction (frozen policy) | - | 7 | 0.00% | 36.84% | 73.75% | 73.75% | 26.25% | 23.47% | false |
| s1_strong_signal | 2. BH FDR | - | 6 | 0.00% | 31.58% | 69.22% | 69.22% | 30.78% | 23.47% | false |
| s1_strong_signal | 3. BH + conservative-effect floor | 0.010000 | 6 | 0.00% | 31.58% | 69.22% | 69.22% | 30.78% | 23.47% | false |
| s1_strong_signal | 3. BH + conservative-effect floor | 0.030000 | 6 | 0.00% | 31.58% | 69.22% | 69.22% | 30.78% | 23.47% | false |
| s1_strong_signal | 3. BH + conservative-effect floor | 0.050000 | 2 | 0.00% | 10.53% | 37.85% | 37.85% | 62.15% | 23.47% | false |
| s1_strong_signal | 3. BH + conservative-effect floor | 0.100000 | 1 | 0.00% | 5.26% | 23.47% | 23.47% | 76.53% | 23.47% | false |
| s1_strong_signal | 3. BH + conservative-effect floor | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s1_strong_signal | 4. floor only (no multiplicity correction) | 0.010000 | 7 | 0.00% | 36.84% | 73.75% | 73.75% | 26.25% | 23.47% | false |
| s1_strong_signal | 4. floor only (no multiplicity correction) | 0.030000 | 6 | 0.00% | 31.58% | 69.22% | 69.22% | 30.78% | 23.47% | false |
| s1_strong_signal | 4. floor only (no multiplicity correction) | 0.050000 | 2 | 0.00% | 10.53% | 37.85% | 37.85% | 62.15% | 23.47% | false |
| s1_strong_signal | 4. floor only (no multiplicity correction) | 0.100000 | 1 | 0.00% | 5.26% | 23.47% | 23.47% | 76.53% | 23.47% | false |
| s1_strong_signal | 4. floor only (no multiplicity correction) | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s1_strong_signal | 5. per-cohort cap only | 25.0%B | 7 | 0.00% | 36.84% | 73.75% | 73.75% | 26.25% | 23.47% | false |
| s1_strong_signal | 5. per-cohort cap only | 10.0%B | 7 | 0.00% | 36.84% | 55.90% | 55.90% | 44.10% | 10.00% | false |
| s1_strong_signal | 5. per-cohort cap only | 5.0%B | 7 | 0.00% | 36.84% | 34.53% | 34.53% | 65.47% | 5.00% | false |
| s1_strong_signal | 5. per-cohort cap only | 2.5%B | 7 | 0.00% | 36.84% | 17.50% | 17.50% | 82.50% | 2.50% | false |
| s1_strong_signal | 6. C-R curve recalibration (proportional) | x1/2 | 7 | 0.00% | 36.84% | 36.88% | 36.88% | 63.12% | 11.74% | false |
| s1_strong_signal | 6. C-R curve recalibration (proportional) | x1/4 | 7 | 0.00% | 36.84% | 18.44% | 18.44% | 81.56% | 5.87% | false |
| s1_strong_signal | 6. C-R curve recalibration (proportional) | x1/12 | 7 | 0.00% | 36.84% | 6.15% | 6.15% | 93.85% | 1.96% | false |
| s1_strong_signal | 6b. C-R recalibration as curve SATURATION (== arm 5) | 25.0%B | 7 | 0.00% | 36.84% | 73.75% | 73.75% | 26.25% | 23.47% | false |
| s1_strong_signal | 6b. C-R recalibration as curve SATURATION (== arm 5) | 10.0%B | 7 | 0.00% | 36.84% | 55.90% | 55.90% | 44.10% | 10.00% | false |
| s1_strong_signal | 6b. C-R recalibration as curve SATURATION (== arm 5) | 5.0%B | 7 | 0.00% | 36.84% | 34.53% | 34.53% | 65.47% | 5.00% | false |
| s1_strong_signal | 6b. C-R recalibration as curve SATURATION (== arm 5) | 2.5%B | 7 | 0.00% | 36.84% | 17.50% | 17.50% | 82.50% | 2.50% | false |
| s1_strong_signal | 7. BH + per-cohort cap | 25.0%B | 6 | 0.00% | 31.58% | 69.22% | 69.22% | 30.78% | 23.47% | false |
| s1_strong_signal | 7. BH + per-cohort cap | 10.0%B | 6 | 0.00% | 31.58% | 51.37% | 51.37% | 48.63% | 10.00% | false |
| s1_strong_signal | 7. BH + per-cohort cap | 5.0%B | 6 | 0.00% | 31.58% | 30.00% | 30.00% | 70.00% | 5.00% | false |
| s1_strong_signal | 7. BH + per-cohort cap | 2.5%B | 6 | 0.00% | 31.58% | 15.00% | 15.00% | 85.00% | 2.50% | false |
| s2_null_effect | 1. no correction (frozen policy) | - | 2 | 29.61% | n/a | 0.00% | 29.61% | 70.39% | 25.94% | false |
| s2_null_effect | 2. BH FDR | - | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 3. BH + conservative-effect floor | 0.010000 | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 3. BH + conservative-effect floor | 0.030000 | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 3. BH + conservative-effect floor | 0.050000 | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 3. BH + conservative-effect floor | 0.100000 | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 3. BH + conservative-effect floor | 0.150000 | 0 | 0.00% | n/a | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s2_null_effect | 4. floor only (no multiplicity correction) | 0.010000 | 2 | 29.61% | n/a | 0.00% | 29.61% | 70.39% | 25.94% | false |
| s2_null_effect | 4. floor only (no multiplicity correction) | 0.030000 | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 4. floor only (no multiplicity correction) | 0.050000 | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 4. floor only (no multiplicity correction) | 0.100000 | 1 | 25.94% | n/a | 0.00% | 25.94% | 74.06% | 25.94% | false |
| s2_null_effect | 4. floor only (no multiplicity correction) | 0.150000 | 0 | 0.00% | n/a | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s2_null_effect | 5. per-cohort cap only | 25.0%B | 2 | 28.68% | n/a | 0.00% | 28.68% | 71.32% | 25.00% | false |
| s2_null_effect | 5. per-cohort cap only | 10.0%B | 2 | 13.68% | n/a | 0.00% | 13.68% | 86.32% | 10.00% | false |
| s2_null_effect | 5. per-cohort cap only | 5.0%B | 2 | 8.68% | n/a | 0.00% | 8.68% | 91.32% | 5.00% | false |
| s2_null_effect | 5. per-cohort cap only | 2.5%B | 2 | 5.00% | n/a | 0.00% | 5.00% | 95.00% | 2.50% | false |
| s2_null_effect | 6. C-R curve recalibration (proportional) | x1/2 | 2 | 14.81% | n/a | 0.00% | 14.81% | 85.19% | 12.97% | false |
| s2_null_effect | 6. C-R curve recalibration (proportional) | x1/4 | 2 | 7.40% | n/a | 0.00% | 7.40% | 92.60% | 6.48% | false |
| s2_null_effect | 6. C-R curve recalibration (proportional) | x1/12 | 2 | 2.47% | n/a | 0.00% | 2.47% | 97.53% | 2.16% | false |
| s2_null_effect | 6b. C-R recalibration as curve SATURATION (== arm 5) | 25.0%B | 2 | 28.68% | n/a | 0.00% | 28.68% | 71.32% | 25.00% | false |
| s2_null_effect | 6b. C-R recalibration as curve SATURATION (== arm 5) | 10.0%B | 2 | 13.68% | n/a | 0.00% | 13.68% | 86.32% | 10.00% | false |
| s2_null_effect | 6b. C-R recalibration as curve SATURATION (== arm 5) | 5.0%B | 2 | 8.68% | n/a | 0.00% | 8.68% | 91.32% | 5.00% | false |
| s2_null_effect | 6b. C-R recalibration as curve SATURATION (== arm 5) | 2.5%B | 2 | 5.00% | n/a | 0.00% | 5.00% | 95.00% | 2.50% | false |
| s2_null_effect | 7. BH + per-cohort cap | 25.0%B | 1 | 25.00% | n/a | 0.00% | 25.00% | 75.00% | 25.00% | false |
| s2_null_effect | 7. BH + per-cohort cap | 10.0%B | 1 | 10.00% | n/a | 0.00% | 10.00% | 90.00% | 10.00% | false |
| s2_null_effect | 7. BH + per-cohort cap | 5.0%B | 1 | 5.00% | n/a | 0.00% | 5.00% | 95.00% | 5.00% | false |
| s2_null_effect | 7. BH + per-cohort cap | 2.5%B | 1 | 2.50% | n/a | 0.00% | 2.50% | 97.50% | 2.50% | false |
| s3_low_power | 1. no correction (frozen policy) | - | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 2. BH FDR | - | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 3. BH + conservative-effect floor | 0.010000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 3. BH + conservative-effect floor | 0.030000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 3. BH + conservative-effect floor | 0.050000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 3. BH + conservative-effect floor | 0.100000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 3. BH + conservative-effect floor | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 4. floor only (no multiplicity correction) | 0.010000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 4. floor only (no multiplicity correction) | 0.030000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 4. floor only (no multiplicity correction) | 0.050000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 4. floor only (no multiplicity correction) | 0.100000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 4. floor only (no multiplicity correction) | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 5. per-cohort cap only | 25.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 5. per-cohort cap only | 10.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 5. per-cohort cap only | 5.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 5. per-cohort cap only | 2.5%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 6. C-R curve recalibration (proportional) | x1/2 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 6. C-R curve recalibration (proportional) | x1/4 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 6. C-R curve recalibration (proportional) | x1/12 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 6b. C-R recalibration as curve SATURATION (== arm 5) | 25.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 6b. C-R recalibration as curve SATURATION (== arm 5) | 10.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 6b. C-R recalibration as curve SATURATION (== arm 5) | 5.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 6b. C-R recalibration as curve SATURATION (== arm 5) | 2.5%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 7. BH + per-cohort cap | 25.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 7. BH + per-cohort cap | 10.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 7. BH + per-cohort cap | 5.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s3_low_power | 7. BH + per-cohort cap | 2.5%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s4_interference | 1. no correction (frozen policy) | - | 8 | 0.00% | 36.36% | 100.00% | 100.00% | 0.00% | 28.31% | true |
| s4_interference | 2. BH FDR | - | 6 | 0.00% | 27.27% | 100.00% | 100.00% | 0.00% | 29.71% | true |
| s4_interference | 3. BH + conservative-effect floor | 0.010000 | 6 | 0.00% | 27.27% | 100.00% | 100.00% | 0.00% | 29.71% | true |
| s4_interference | 3. BH + conservative-effect floor | 0.030000 | 6 | 0.00% | 27.27% | 100.00% | 100.00% | 0.00% | 29.71% | true |
| s4_interference | 3. BH + conservative-effect floor | 0.050000 | 4 | 0.00% | 18.18% | 83.25% | 83.25% | 16.75% | 30.15% | false |
| s4_interference | 3. BH + conservative-effect floor | 0.100000 | 3 | 0.00% | 13.64% | 72.50% | 72.50% | 27.50% | 30.15% | false |
| s4_interference | 3. BH + conservative-effect floor | 0.150000 | 1 | 0.00% | 4.55% | 30.15% | 30.15% | 69.85% | 30.15% | false |
| s4_interference | 4. floor only (no multiplicity correction) | 0.010000 | 7 | 0.00% | 31.82% | 100.00% | 100.00% | 0.00% | 28.36% | true |
| s4_interference | 4. floor only (no multiplicity correction) | 0.030000 | 6 | 0.00% | 27.27% | 100.00% | 100.00% | 0.00% | 29.71% | true |
| s4_interference | 4. floor only (no multiplicity correction) | 0.050000 | 4 | 0.00% | 18.18% | 83.25% | 83.25% | 16.75% | 30.15% | false |
| s4_interference | 4. floor only (no multiplicity correction) | 0.100000 | 3 | 0.00% | 13.64% | 72.50% | 72.50% | 27.50% | 30.15% | false |
| s4_interference | 4. floor only (no multiplicity correction) | 0.150000 | 1 | 0.00% | 4.55% | 30.15% | 30.15% | 69.85% | 30.15% | false |
| s4_interference | 5. per-cohort cap only | 25.0%B | 8 | 0.00% | 36.36% | 100.00% | 100.00% | 0.00% | 24.67% | true |
| s4_interference | 5. per-cohort cap only | 10.0%B | 8 | 0.00% | 36.36% | 63.24% | 63.24% | 36.76% | 10.00% | false |
| s4_interference | 5. per-cohort cap only | 5.0%B | 8 | 0.00% | 36.36% | 35.03% | 35.03% | 64.97% | 5.00% | false |
| s4_interference | 5. per-cohort cap only | 2.5%B | 8 | 0.00% | 36.36% | 17.70% | 17.70% | 82.30% | 2.50% | false |
| s4_interference | 6. C-R curve recalibration (proportional) | x1/2 | 8 | 0.00% | 36.36% | 53.25% | 53.25% | 46.75% | 15.07% | false |
| s4_interference | 6. C-R curve recalibration (proportional) | x1/4 | 8 | 0.00% | 36.36% | 26.62% | 26.62% | 73.38% | 7.54% | false |
| s4_interference | 6. C-R curve recalibration (proportional) | x1/12 | 8 | 0.00% | 36.36% | 8.87% | 8.87% | 91.13% | 2.51% | false |
| s4_interference | 6b. C-R recalibration as curve SATURATION (== arm 5) | 25.0%B | 8 | 0.00% | 36.36% | 100.00% | 100.00% | 0.00% | 24.67% | true |
| s4_interference | 6b. C-R recalibration as curve SATURATION (== arm 5) | 10.0%B | 8 | 0.00% | 36.36% | 63.24% | 63.24% | 36.76% | 10.00% | false |
| s4_interference | 6b. C-R recalibration as curve SATURATION (== arm 5) | 5.0%B | 8 | 0.00% | 36.36% | 35.03% | 35.03% | 64.97% | 5.00% | false |
| s4_interference | 6b. C-R recalibration as curve SATURATION (== arm 5) | 2.5%B | 8 | 0.00% | 36.36% | 17.70% | 17.70% | 82.30% | 2.50% | false |
| s4_interference | 7. BH + per-cohort cap | 25.0%B | 6 | 0.00% | 27.27% | 96.31% | 96.31% | 3.69% | 25.00% | false |
| s4_interference | 7. BH + per-cohort cap | 10.0%B | 6 | 0.00% | 27.27% | 58.21% | 58.21% | 41.79% | 10.00% | false |
| s4_interference | 7. BH + per-cohort cap | 5.0%B | 6 | 0.00% | 27.27% | 30.00% | 30.00% | 70.00% | 5.00% | false |
| s4_interference | 7. BH + per-cohort cap | 2.5%B | 6 | 0.00% | 27.27% | 15.00% | 15.00% | 85.00% | 2.50% | false |
| s5_sybil_contamination | 1. no correction (frozen policy) | - | 10 | 0.00% | 62.50% | 81.93% | 81.93% | 18.07% | 23.23% | false |
| s5_sybil_contamination | 2. BH FDR | - | 6 | 0.00% | 37.50% | 76.31% | 76.31% | 23.69% | 23.23% | false |
| s5_sybil_contamination | 3. BH + conservative-effect floor | 0.010000 | 6 | 0.00% | 37.50% | 76.31% | 76.31% | 23.69% | 23.23% | false |
| s5_sybil_contamination | 3. BH + conservative-effect floor | 0.030000 | 5 | 0.00% | 31.25% | 71.02% | 71.02% | 28.98% | 23.23% | false |
| s5_sybil_contamination | 3. BH + conservative-effect floor | 0.050000 | 3 | 0.00% | 18.75% | 57.32% | 57.32% | 42.68% | 23.23% | false |
| s5_sybil_contamination | 3. BH + conservative-effect floor | 0.100000 | 1 | 0.00% | 6.25% | 23.23% | 23.23% | 76.77% | 23.23% | false |
| s5_sybil_contamination | 3. BH + conservative-effect floor | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s5_sybil_contamination | 4. floor only (no multiplicity correction) | 0.010000 | 7 | 0.00% | 43.75% | 79.45% | 79.45% | 20.55% | 23.23% | false |
| s5_sybil_contamination | 4. floor only (no multiplicity correction) | 0.030000 | 5 | 0.00% | 31.25% | 71.02% | 71.02% | 28.98% | 23.23% | false |
| s5_sybil_contamination | 4. floor only (no multiplicity correction) | 0.050000 | 3 | 0.00% | 18.75% | 57.32% | 57.32% | 42.68% | 23.23% | false |
| s5_sybil_contamination | 4. floor only (no multiplicity correction) | 0.100000 | 1 | 0.00% | 6.25% | 23.23% | 23.23% | 76.77% | 23.23% | false |
| s5_sybil_contamination | 4. floor only (no multiplicity correction) | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s5_sybil_contamination | 5. per-cohort cap only | 25.0%B | 10 | 0.00% | 62.50% | 81.93% | 81.93% | 18.07% | 23.23% | false |
| s5_sybil_contamination | 5. per-cohort cap only | 10.0%B | 10 | 0.00% | 62.50% | 54.61% | 54.61% | 45.39% | 10.00% | false |
| s5_sybil_contamination | 5. per-cohort cap only | 5.0%B | 10 | 0.00% | 62.50% | 35.62% | 35.62% | 64.38% | 5.00% | false |
| s5_sybil_contamination | 5. per-cohort cap only | 2.5%B | 10 | 0.00% | 62.50% | 19.98% | 19.98% | 80.02% | 2.50% | false |
| s5_sybil_contamination | 6. C-R curve recalibration (proportional) | x1/2 | 10 | 0.00% | 62.50% | 40.97% | 40.97% | 59.03% | 11.61% | false |
| s5_sybil_contamination | 6. C-R curve recalibration (proportional) | x1/4 | 10 | 0.00% | 62.50% | 20.48% | 20.48% | 79.52% | 5.81% | false |
| s5_sybil_contamination | 6. C-R curve recalibration (proportional) | x1/12 | 10 | 0.00% | 62.50% | 6.83% | 6.83% | 93.17% | 1.94% | false |
| s5_sybil_contamination | 6b. C-R recalibration as curve SATURATION (== arm 5) | 25.0%B | 10 | 0.00% | 62.50% | 81.93% | 81.93% | 18.07% | 23.23% | false |
| s5_sybil_contamination | 6b. C-R recalibration as curve SATURATION (== arm 5) | 10.0%B | 10 | 0.00% | 62.50% | 54.61% | 54.61% | 45.39% | 10.00% | false |
| s5_sybil_contamination | 6b. C-R recalibration as curve SATURATION (== arm 5) | 5.0%B | 10 | 0.00% | 62.50% | 35.62% | 35.62% | 64.38% | 5.00% | false |
| s5_sybil_contamination | 6b. C-R recalibration as curve SATURATION (== arm 5) | 2.5%B | 10 | 0.00% | 62.50% | 19.98% | 19.98% | 80.02% | 2.50% | false |
| s5_sybil_contamination | 7. BH + per-cohort cap | 25.0%B | 6 | 0.00% | 37.50% | 76.31% | 76.31% | 23.69% | 23.23% | false |
| s5_sybil_contamination | 7. BH + per-cohort cap | 10.0%B | 6 | 0.00% | 37.50% | 48.98% | 48.98% | 51.02% | 10.00% | false |
| s5_sybil_contamination | 7. BH + per-cohort cap | 5.0%B | 6 | 0.00% | 37.50% | 30.00% | 30.00% | 70.00% | 5.00% | false |
| s5_sybil_contamination | 7. BH + per-cohort cap | 2.5%B | 6 | 0.00% | 37.50% | 15.00% | 15.00% | 85.00% | 2.50% | false |
| s6_demand_shift | 1. no correction (frozen policy) | - | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 2. BH FDR | - | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 3. BH + conservative-effect floor | 0.010000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 3. BH + conservative-effect floor | 0.030000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 3. BH + conservative-effect floor | 0.050000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 3. BH + conservative-effect floor | 0.100000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 3. BH + conservative-effect floor | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 4. floor only (no multiplicity correction) | 0.010000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 4. floor only (no multiplicity correction) | 0.030000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 4. floor only (no multiplicity correction) | 0.050000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 4. floor only (no multiplicity correction) | 0.100000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 4. floor only (no multiplicity correction) | 0.150000 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 5. per-cohort cap only | 25.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 5. per-cohort cap only | 10.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 5. per-cohort cap only | 5.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 5. per-cohort cap only | 2.5%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 6. C-R curve recalibration (proportional) | x1/2 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 6. C-R curve recalibration (proportional) | x1/4 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 6. C-R curve recalibration (proportional) | x1/12 | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 6b. C-R recalibration as curve SATURATION (== arm 5) | 25.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 6b. C-R recalibration as curve SATURATION (== arm 5) | 10.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 6b. C-R recalibration as curve SATURATION (== arm 5) | 5.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 6b. C-R recalibration as curve SATURATION (== arm 5) | 2.5%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 7. BH + per-cohort cap | 25.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 7. BH + per-cohort cap | 10.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 7. BH + per-cohort cap | 5.0%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |
| s6_demand_shift | 7. BH + per-cohort cap | 2.5%B | 0 | 0.00% | 0.00% | 0.00% | 0.00% | 100.00% | 0.00% | false |

### The tradeoff, on one line per lever setting

Null waste and null concentration are measured on `s2_null_effect`; power is the head-count on the two clean-signal scenarios (`s1`, `s5`), the interference scenario (`s4`), and the two weak-but-real scenarios (`s3_low_power`, `s6_demand_shift`) that are our #1 risk-register item. `s1 legit` is what the lever costs a network that genuinely delivered.

| lever setting | s2 waste | s2 max share | s1 power | s4 power | s5 power | s3 power | s6 power | s1 legit (%B) | s2 waste / s1 legit |
|---|---|---|---|---|---|---|---|---|---|
| 1. baseline (frozen policy) | 29.61% | 25.94% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 73.75% | 0.402 |
| 2. BH FDR | 25.94% | 25.94% | 31.58% | 27.27% | 37.50% | 0.00% | 0.00% | 69.22% | 0.375 |
| 4. floor 0.010000 | 29.61% | 25.94% | 36.84% | 31.82% | 43.75% | 0.00% | 0.00% | 73.75% | 0.402 |
| 4. floor 0.030000 | 25.94% | 25.94% | 31.58% | 27.27% | 31.25% | 0.00% | 0.00% | 69.22% | 0.375 |
| 4. floor 0.050000 | 25.94% | 25.94% | 10.53% | 18.18% | 18.75% | 0.00% | 0.00% | 37.85% | 0.685 |
| 4. floor 0.100000 | 25.94% | 25.94% | 5.26% | 13.64% | 6.25% | 0.00% | 0.00% | 23.47% | 1.105 |
| 4. floor 0.150000 | 0.00% | 0.00% | 0.00% | 4.55% | 0.00% | 0.00% | 0.00% | 0.00% | n/a |
| 3. BH + floor 0.010000 | 25.94% | 25.94% | 31.58% | 27.27% | 37.50% | 0.00% | 0.00% | 69.22% | 0.375 |
| 3. BH + floor 0.030000 | 25.94% | 25.94% | 31.58% | 27.27% | 31.25% | 0.00% | 0.00% | 69.22% | 0.375 |
| 3. BH + floor 0.050000 | 25.94% | 25.94% | 10.53% | 18.18% | 18.75% | 0.00% | 0.00% | 37.85% | 0.685 |
| 3. BH + floor 0.100000 | 25.94% | 25.94% | 5.26% | 13.64% | 6.25% | 0.00% | 0.00% | 23.47% | 1.105 |
| 3. BH + floor 0.150000 | 0.00% | 0.00% | 0.00% | 4.55% | 0.00% | 0.00% | 0.00% | 0.00% | n/a |
| 5. cap 25.0%B | 28.68% | 25.00% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 73.75% | 0.389 |
| 5. cap 10.0%B | 13.68% | 10.00% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 55.90% | 0.245 |
| 5. cap 5.0%B | 8.68% | 5.00% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 34.53% | 0.251 |
| 5. cap 2.5%B | 5.00% | 2.50% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 17.50% | 0.286 |
| 6. C-R recalibrate x1/2 | 14.81% | 12.97% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 36.88% | 0.402 |
| 6. C-R recalibrate x1/4 | 7.40% | 6.48% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 18.44% | 0.402 |
| 6. C-R recalibrate x1/12 | 2.47% | 2.16% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 6.15% | 0.402 |
| 6b. C-R saturate at 25.0%B | 28.68% | 25.00% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 73.75% | 0.389 |
| 6b. C-R saturate at 10.0%B | 13.68% | 10.00% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 55.90% | 0.245 |
| 6b. C-R saturate at 5.0%B | 8.68% | 5.00% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 34.53% | 0.251 |
| 6b. C-R saturate at 2.5%B | 5.00% | 2.50% | 36.84% | 36.36% | 62.50% | 0.00% | 0.00% | 17.50% | 0.286 |
| 7. BH + cap 25.0%B | 25.00% | 25.00% | 31.58% | 27.27% | 37.50% | 0.00% | 0.00% | 69.22% | 0.361 |
| 7. BH + cap 10.0%B | 10.00% | 10.00% | 31.58% | 27.27% | 37.50% | 0.00% | 0.00% | 51.37% | 0.195 |
| 7. BH + cap 5.0%B | 5.00% | 5.00% | 31.58% | 27.27% | 37.50% | 0.00% | 0.00% | 30.00% | 0.167 |
| 7. BH + cap 2.5%B | 2.50% | 2.50% | 31.58% | 27.27% | 37.50% | 0.00% | 0.00% | 15.00% | 0.167 |

The last column is the efficiency frontier: **null dollars bought per legitimate dollar deployed**, lower is better. It is the only column that is invariant to simply spending less, which is what separates a real targeting improvement from a `value_scale` change.

## Verdict: the structural cap dominates — and it costs NO frozen field, because it is a reward-curve shape

Judged on `s2` null waste AND on `s2` concentration AND on power for the genuinely-weak-but-real scenarios (`s3_low_power`, `s6_demand_shift`), in the order the risk register cares about.

**1. The floor and BH are REDUNDANT at every proposed parameter — measured, not derived.** `s2`'s two payers sit at `conservative_s` = **0.139576** (`cell0007`, 25.94% of `B`) and **0.018384** (`cell0048`, 3.68% of `B`). Any floor between those two values removes the small payer and only the small payer — which is exactly the cohort BH already removes. The table confirms it: BH alone, `floor 0.030000`, `floor 0.050000`, `floor 0.100000`, and every `BH + floor` up to `0.100000` all land on the identical `s2` waste of **25.94%** and the identical max share of **25.94%**. **At the proposed parameters the floor buys nothing that BH does not already buy, and BH buys nothing that the floor does not already buy.** They are the same lever wearing two hats; adopting both would be paying twice for one effect.

**And NO floor value beats recalibration.** The floor sweep spans below, at and above the weak-but-real effects (`s3` = 0.030, `s6` = 0.050). The only grid floor that drives `s2` waste below 25.94% is `0.150000` — which drives it to 0.00% by removing the false positive, but simultaneously drives `s1` power to 0.00%, `s5` to 0.00% and `s4` to 4.55%. It removes the signal before it removes the noise, because the pure-null cohort's conservative effect (0.139576) is LARGER than any true-positive cohort's in the entire benchmark. There is no floor value that separates them, at any granularity, because they are not separated on this axis at all.

**2. The per-cohort cap is the only lever that cuts null spend without dropping a single true positive.** `s2` waste 29.61% -> 13.68% (`10.0%B`) -> 8.68% (`5.0%B`) -> 5.00% (`2.5%B`), and the concentration channel closes with it: max single-cohort share 25.94% -> 10.00% -> 5.00% -> 2.50%. The paid SET is unchanged at every cap: `s1` power stays 36.84%, `s4` 36.36%, `s5` 62.50%. BH, by contrast, buys 29.61% -> 25.94% of waste, leaves max share at 25.94%, and pays for it with `s1` power 36.84% -> 31.58% and `s5` 62.50% -> 37.50%.

That is a structural guarantee, not a lucky draw. With a cap `k`, null spend is bounded by `(number of nulls that clear the test) * k` on ANY realization — distribution-free, no independence assumption, no calibrated p-value. BH bounds only a *count*, and this study shows how weak that is as a spend bound: the count falls 2 -> 1 while spend falls only 29.61% -> 25.94%, because the survivor is the large one.

**3. C-R recalibration is real, is large, and is NOT a targeting improvement.** The architect's calibration defect is confirmed: the example curve's first paying breakpoint pays 20.00% of the whole budget to ONE cohort where an equal share across the declared 60 cohorts is 1.67%, i.e. the curve is mis-scaled by ~12x. Applying the equal-share calibration (`x1/12`) cuts `s2` waste 29.61% -> **2.47%** and max single-cohort share 25.94% -> **2.16%** at ZERO power cost — `s1` 36.84%, `s4` 36.36%, `s5` 62.50%, all unchanged from baseline. On the headline numbers it is the single largest improvement in the study.

**But the efficiency column says plainly what it is.** A proportional rescale multiplies every allocation by the same rational, so in the `S <= B` branch it multiplies waste and legitimate spend *equally* — it cannot change their ratio, and the measurement confirms the algebra to three decimals: `s2 waste / s1 legit` is 0.402 at baseline, 0.402 at `x1/4`, 0.402 at `x1/12`. C-R recalibration reduces EXPOSURE, not mis-targeting. It is a `value_scale` correction, and it should be adopted on those grounds — the curve genuinely is mis-calibrated by an order of magnitude against the cohort count — but it must not be sold as a false-positive remedy. Contrast the cap, which binds harder on the concentrated null than on the dispersed signal and therefore does move the ratio: 0.402 at baseline, 0.245 at `10.0%B`, 0.286 at `2.5%B` — a genuine targeting gain, bottoming out around a `10.0%B` ceiling and worsening again once the cap starts biting the true positives too.

At MATCHED legitimate spend the cap strictly dominates recalibration: `cap 2.5%B` deploys 17.50% of `B` to `s1`'s true positives for 5.00% of `s2` waste, while `C-R x1/4` deploys a comparable 18.44% for 7.40% of waste. Same money to the honest network, materially less to the null.

**4. The finding that closes the v1.2 question: the cap needs NO new frozen field.** Arm 6b applies the identical ceiling as a *saturation of the reward curve* — insert the crossing breakpoint, then hold flat — and recompiles a real manifest with new breakpoints and a recomputed `reward_curve_hash`. It reproduces the post-hoc cap **exactly** at every ceiling whose crossing point is integral on this curve (`10.0%B`, `5.0%B`, `2.5%B`: identical to the ppm on all six scenarios), and is short by 1 ppm at `25.0%B` where the crossing is not integral — short, never over, since the construction rounds the crossing up. So a per-cohort cap is expressible **today**, inside the existing frozen schema, as a different `reward_curve` fixture. It is not a new manifest field, it does not move `manifest_hash` `74e0bb82…` for anyone who does not opt in, and it needs no v1.2 migration. The same is true of C-R recalibration: the benchmark curve lives in `specs/examples/manifest.example.json`, a FIXTURE, not a protocol constant.

This retires the framing of the open question. It was posed as "which ONE frozen field do we spend in v1.2 — an FDR level, a floor, or a cap?". The answer is **none of them**: the two levers worth having (cap, recalibration) are both reward-curve shapes, and the reward curve is already frozen per experiment. The only lever that would genuinely need a new frozen field is the FDR level — and it is the weakest of the three on this evidence.

**5. `s3_low_power` and `s6_demand_shift` pay zero under EVERY lever, including the baseline.** No lever crushes them, because there is nothing left to crush — they are already at zero paid cohorts and 100% recovered budget before any lever is applied — and no lever rescues them. Their zero is a fact about per-cohort power in a whole-cohort design where each cohort contributes a single cluster draw whose noise SD is the same order as the effect being sought (`s3` true effect 0.030, `s6` 0.050, against a conservative margin of ~0.10 on every scenario). Reporting that plainly is required (CLAUDE.md invariant 8); no threshold, floor, cap or curve should be tuned to change it. The lever that *would* change it is a DESIGN change — switchback or repeated re-randomization, so a cohort's own cluster noise differences out — not a policy field. One consequence worth stating: because `s3`/`s6` are at zero in every arm, this study **cannot** rank the levers on weak-signal power. It can only certify that none of them makes that outcome worse.

**Recommendation to the architect (I do not decide this).** Ranked: **(1) C-R curve recalibration** — adopt it, it is a genuine and large calibration defect, it costs no spec change and no power, but book it as an exposure fix, not a false-positive fix. **(2) per-cohort cap, expressed as curve saturation** — the only lever that improves targeting per dollar (`s2 waste / s1 legit` 0.402 at baseline, bottoming at 0.245 around a `10.0%B` ceiling), with a distribution-free bound, and also no spec change. The two compose: recalibrate the scale, saturate the shape. **(3) BH** — buys 29.61% -> 25.94% of waste, leaves the concentration channel untouched at 25.94%, costs `s5` power 62.50% -> 37.50%, and is the only candidate that would actually require a new frozen field. **(4) conservative-effect floor** — dominated and redundant; do not spend anything on it. Secondary, cheap: with G0 = 30 control cohorts the frozen `critical_value_reference = normal_approx` (1.645) is mildly anticonservative against `t_29` (1.699); it would not have stopped the false positive above, but it is a low-cost correction if v1.2 opens for another reason.

**Caveat, stated once and meant.** Every number above is ONE draw of ONE committed seed on a simulated network. The cap's bound is the only claim here that holds by construction; the rest is a single realization and should be read as such.
