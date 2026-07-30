# Compensation study: does the recommended curve spend WELL on signal, or merely spend little?

**Status:** benchmark-report material feeding the `protocol-architect` recommendation, and the answer to the treasury owner's CONDITION 1 on `docs/multiplicity-study.md`. Study-only: nothing here changes a shipped default, a frozen field, or the reward goldens. It runs the SAME absolute-scale compiler (unused budget recovered), through genuinely recompiled manifests (new breakpoints, recomputed `reward_curve_hash`).

Regenerate deterministically: `python -m crp_engine.studies compensation` (or `python tools/compensation_study.py`). Same committed simulator artifacts + committed seed `0000000000000000000000000000000000000000000000000123456789abcdef` => identical numbers across fresh processes.

## Why this document exists

`docs/multiplicity-study.md` reported the recalibration win as "`s2` null waste 29.61% -> 2.47% at zero power cost". **Power there is a head-count** — the SHARE of true-positive cohorts that are paid ANYTHING. It is binary; it does not capture how much they are paid. A proportional recalibration multiplies every allocation by the same rational, so it cuts null spend and legitimate payout *by the same factor*. The head-count stays flat (a cohort paid a twelfth of its due is still "paid"), so the prior study could not see the cost. A treasury's failure mode is spending BADLY, not spending little — under-deploying on a genuinely high-signal network is a real cost even though `close_experiment` recovers the funds. This document measures that cost.

## Method

- **Candidate curves.** `shipped` = the frozen benchmark curve. `recal_es` = the equal-share recalibration (the prior recommendation, per-scenario scale `5/N`). `recal_es+cap10` = that recalibration plus a 10%B saturation cap. `cap10` / `cap5` / `cap2.5` = the shipped curve saturated at 10 / 5 / 2.5 %B (the frontier). A cap is a reward-curve SHAPE (`saturate_curve`), so every candidate is a plain `reward_curve` fixture — no new frozen field.
- **legit (base units).** Absolute payout reaching TRUE-POSITIVE cohorts. On the homogeneous-label scenarios all deployed budget is legitimate on a true-positive scenario and all of it is waste on the true-null scenario, so `legit` equals `deployed` on `s1`, `s4`, `s5` and equals 0 on `s2`.
- **deployed vs recovered.** `deployed` = `sum(budget_c)`; `recovered` = `B - deployed`, returned to the treasury by `unused_budget_policy = recoverable`. Under-deployment shows up here as a large `recovered` on a high-signal scenario.
- **ppute (payout per unit true effect).** `legit_base_units` per 1.0 of aggregate delivered true effect, where aggregate true effect = mean realized per-cohort effect (simulator ground truth `mean_cohort_effect`, quantized once to micro units) x the count of payable true-positive cohorts. It is the compensation analogue of the arm study's `waste / legit` efficiency column: a fixed-per-scenario denominator, so across curves it tracks payout for one fixed amount of real signal. Undefined (`n/a`) on `s2` (no true effect).

## Results: compensation across scenarios x candidate curves

| scenario | curve | paid | power | legit (base units) | legit (%B) | deployed (%B) | recovered (%B) | waste (%B) | max share (%B) | ppute (base/effect) |
|---|---|---|---|---|---|---|---|---|---|---|
| s1_strong_signal | shipped (frozen curve) | 7 | 36.84% | 73751750000 | 73.75% | 73.75% | 26.25% | 0.00% | 23.47% | 26767376151 |
| s1_strong_signal | recal equal-share (prior rec) | 7 | 36.84% | 6145979168 | 6.15% | 6.15% | 93.85% | 0.00% | 1.96% | 2230614679 |
| s1_strong_signal | recal equal-share + cap 10%B | 7 | 36.84% | 6145979168 | 6.15% | 6.15% | 93.85% | 0.00% | 1.96% | 2230614679 |
| s1_strong_signal | cap 10%B  (FINALIZED) | 7 | 36.84% | 55902600000 | 55.90% | 55.90% | 44.10% | 0.00% | 10.00% | 20289225978 |
| s1_strong_signal | cap 5%B | 7 | 36.84% | 34529600000 | 34.53% | 34.53% | 65.47% | 0.00% | 5.00% | 12532133699 |
| s1_strong_signal | cap 2.5%B | 7 | 36.84% | 17500000000 | 17.50% | 17.50% | 82.50% | 0.00% | 2.50% | 6351430069 |
| s2_null_effect | shipped (frozen curve) | 2 | n/a | 0 | 0.00% | 29.61% | 70.39% | 29.61% | 25.94% | n/a |
| s2_null_effect | recal equal-share (prior rec) | 2 | n/a | 0 | 0.00% | 2.47% | 97.53% | 2.47% | 2.16% | n/a |
| s2_null_effect | recal equal-share + cap 10%B | 2 | n/a | 0 | 0.00% | 2.47% | 97.53% | 2.47% | 2.16% | n/a |
| s2_null_effect | cap 10%B  (FINALIZED) | 2 | n/a | 0 | 0.00% | 13.68% | 86.32% | 13.68% | 10.00% | n/a |
| s2_null_effect | cap 5%B | 2 | n/a | 0 | 0.00% | 8.68% | 91.32% | 8.68% | 5.00% | n/a |
| s2_null_effect | cap 2.5%B | 2 | n/a | 0 | 0.00% | 5.00% | 95.00% | 5.00% | 2.50% | n/a |
| s3_low_power | shipped (frozen curve) | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s3_low_power | recal equal-share (prior rec) | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s3_low_power | recal equal-share + cap 10%B | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s3_low_power | cap 10%B  (FINALIZED) | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s3_low_power | cap 5%B | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s3_low_power | cap 2.5%B | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s4_interference | shipped (frozen curve) | 8 | 36.36% | 99999999994 | 100.00% | 100.00% | 0.00% | 0.00% | 28.31% | 42029168240 |
| s4_interference | recal equal-share (prior rec) | 8 | 36.36% | 8874208334 | 8.87% | 8.87% | 91.13% | 0.00% | 2.51% | 3729755950 |
| s4_interference | recal equal-share + cap 10%B | 8 | 36.36% | 8874208334 | 8.87% | 8.87% | 91.13% | 0.00% | 2.51% | 3729755950 |
| s4_interference | cap 10%B  (FINALIZED) | 8 | 36.36% | 63237800000 | 63.24% | 63.24% | 36.76% | 0.00% | 10.00% | 26578321355 |
| s4_interference | cap 5%B | 8 | 36.36% | 35031800000 | 35.03% | 35.03% | 64.97% | 0.00% | 5.00% | 14723574160 |
| s4_interference | cap 2.5%B | 8 | 36.36% | 17700800000 | 17.70% | 17.70% | 82.30% | 0.00% | 2.50% | 7439499012 |
| s5_sybil_contamination | shipped (frozen curve) | 10 | 62.50% | 81932350000 | 81.93% | 81.93% | 18.07% | 0.00% | 23.23% | 44295801832 |
| s5_sybil_contamination | recal equal-share (prior rec) | 10 | 62.50% | 6827695835 | 6.83% | 6.83% | 93.17% | 0.00% | 1.94% | 3691316820 |
| s5_sybil_contamination | recal equal-share + cap 10%B | 10 | 62.50% | 6827695835 | 6.83% | 6.83% | 93.17% | 0.00% | 1.94% | 3691316820 |
| s5_sybil_contamination | cap 10%B  (FINALIZED) | 10 | 62.50% | 54608800000 | 54.61% | 54.61% | 45.39% | 0.00% | 10.00% | 29523632400 |
| s5_sybil_contamination | cap 5%B | 10 | 62.50% | 35624000000 | 35.62% | 35.62% | 64.38% | 0.00% | 5.00% | 19259714196 |
| s5_sybil_contamination | cap 2.5%B | 10 | 62.50% | 19983800000 | 19.98% | 19.98% | 80.02% | 0.00% | 2.50% | 10804016297 |
| s6_demand_shift | shipped (frozen curve) | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s6_demand_shift | recal equal-share (prior rec) | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s6_demand_shift | recal equal-share + cap 10%B | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s6_demand_shift | cap 10%B  (FINALIZED) | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s6_demand_shift | cap 5%B | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |
| s6_demand_shift | cap 2.5%B | 0 | 0.00% | 0 | 0.00% | 0.00% | 100.00% | 0.00% | 0.00% | 0 |

## High-signal deployment: the under-deployment channel

The three genuinely high-signal scenarios (`s1_strong_signal`, `s5_sybil_contamination`, `s4_interference`) are where under-deployment is visible. `legit (%B)` is what a network that truly delivered actually receives; `recovered (%B)` is what the treasury hands back on that same high-signal network.

| curve | s1 legit (%B) | s1 recovered | s5 legit (%B) | s5 recovered | s4 legit (%B) | s4 recovered | s2 waste (%B) | s2 max share |
|---|---|---|---|---|---|---|---|---|
| shipped (frozen curve) | 73.75% | 26.25% | 81.93% | 18.07% | 100.00% | 0.00% | 29.61% | 25.94% |
| recal equal-share (prior rec) | 6.15% | 93.85% | 6.83% | 93.17% | 8.87% | 91.13% | 2.47% | 2.16% |
| recal equal-share + cap 10%B | 6.15% | 93.85% | 6.83% | 93.17% | 8.87% | 91.13% | 2.47% | 2.16% |
| cap 10%B  (FINALIZED) | 55.90% | 44.10% | 54.61% | 45.39% | 63.24% | 36.76% | 13.68% | 10.00% |
| cap 5%B | 34.53% | 65.47% | 35.62% | 64.38% | 35.03% | 64.97% | 8.68% | 5.00% |
| cap 2.5%B | 17.50% | 82.50% | 19.98% | 80.02% | 17.70% | 82.30% | 5.00% | 2.50% |

## Verdict: recalibration UNDER-DEPLOYS; the finalized curve is the shipped scale + a 10%B cap

**1. The equal-share recalibration starves high-signal networks — measured.** On `s1_strong_signal` the shipped curve pays true positives **73.75% of `B`** (73751750000 base units); the equal-share recalibration `x1/12` pays **6.15%** (6145979168 base units) and recovers **93.85%** of the budget on a network the benchmark labels strongly positive. On `s5` it is 81.93% -> 6.83%. That is the exact failure mode CONDITION 1 named: the recalibration's "29.61% -> 2.47% null-waste win" is bought by cutting `s1` legitimate payout by the SAME ~12/1 factor, invisible to a head-count because every paid cohort stays "paid". The treasury is not spending better; it is spending less, everywhere, in proportion.

The `ppute` column proves it is a pure exposure change, not a targeting change: `s1` pays 26767376151 base units per unit true effect under the shipped curve and 2230614679 under `x1/12` — the same money-for-signal ratio scaled down, delivering strictly less compensation for the identical delivered effect.

**2. The 10%B cap cuts null waste and closes concentration WITHOUT starving signal.** It trims only the cheques above a credible single-cohort ceiling and recovers the clipped excess (which no one cohort credibly earned), so high-signal deployment stays healthy: `s1` legit 73.75% -> **55.90%**, `s5` 81.93% -> **54.61%** — the treasury still spends more than half its budget on genuine signal. Meanwhile `s2` null waste falls 29.61% -> **13.68%** and the concentration channel is bounded to exactly **10.00%** (no cohort can ever take a quarter of the budget from one noisy draw). Unlike a proportional rescale, the cap binds HARDER on the concentrated null than on the dispersed signal, so it is a genuine targeting gain, not an exposure cut.

**3. Why 10%B and not tighter.** Tightening the cap buys less null waste but at an accelerating cost to genuine payout: `s1` legit 55.90% (cap 10%) -> 34.53% (cap 5%) -> 17.50% (cap 2.5%), while `s2` waste only falls 13.68% -> 8.68% -> 5.00%. The targeting ratio (`s2` waste / `s1` legit, lower better) is **0.245 at 10%B**, worsening to 0.251 at 5% and 0.286 at 2.5% as the cap starts clipping true positives too. 10%B is the frontier point: it both minimizes null waste per legitimate dollar AND preserves the most legitimate deployment. A tighter cap would itself become an under-deployment lever.

## The single finalized recommendation (hand to `protocol-architect`)

**Calibration: keep the shipped curve scale — do NOT apply a proportional recalibration.** The equal-share recalibration is rejected on the evidence above: it under-deploys on genuine signal for no targeting gain. The concentration defect it was meant to fix is fixed by the cap instead, which does it without the collateral under-deployment.

**Structural cap: per-cohort 10.0%B, expressed as a curve saturation.** On the example manifest (`B = 100000000000` base units, `N = 60` declared cohorts) the ceiling is `cap_base_units = 10000000000` (10% of `B`), and the finalized `reward_curve.breakpoints` are:

```
cap_ppm            = 100000            # 10.0% of B
cap_base_units     = 10000000000   # per-cohort ceiling
reward_curve.breakpoints = [(0, 0), (50000, 10000000000), (100000, 10000000000), (500000, 10000000000), (1000000, 10000000000)]
```

This is a valid `piecewise_linear_monotonic` curve (first breakpoint `(0, 0)`, `x` strictly increasing, `y` non-decreasing), so it validates against the frozen schema unchanged and moves no protocol constant. It is a per-experiment `reward_curve` fixture; the architect folds it into the recommendation and the example manifest, and `reward_curve_hash` is recomputed over its canonical bytes as for any curve. For a manifest with a different budget `B'`, the ceiling scales as `cap_base_units = 10% x B'`; the crossing breakpoint `x*` is `curve^-1(ceiling)` on that manifest's own curve. The calibration RULE is "shipped scale, 10%B per-cohort ceiling"; these breakpoints are its instantiation on the example manifest.

**Caveat, meant.** Every number here is ONE draw of ONE committed seed on a simulated network. The cap's concentration bound (`no cohort > 10%B`) holds by construction on any realization; the deployment and waste levels are a single realization and should be read as such.
