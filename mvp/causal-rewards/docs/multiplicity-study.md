# Multiplicity / false-positive study (six scenarios x four regimes)

**Status:** benchmark-report material feeding the `protocol-architect` recommendation (`docs/m3-integration-and-spec-round.md` §2). The frozen default policy is UNCHANGED: `none` (independent one-sided 5% per cohort). Adopting any correction as the default would add a frozen manifest field (an FDR level or a curve floor) and is therefore a hash-moving **v1.2 migration** — not adopted here.

Regenerate deterministically: `python -m crp_engine.studies` (or `python tools/multiplicity_study.py`). Same committed simulator artifacts + committed seed `0000000000000000000000000000000000000000000000000123456789abcdef` => identical numbers across fresh processes.

## Method

- **Regimes.** `none` = current frozen 5% test (this column is the verbatim engine output, `selected_cohorts=None`). `bonferroni` = `p < alpha/m`. `sidak` = `p < 1-(1-alpha)^(1/m)`. `benjamini_hochberg` = the BH (1995) FDR step-up at level `alpha`. `alpha = 0.05`, one-sided; `m` = candidate cohorts (eligible + identified + causal design).
- **p-values.** `p = P(Z >= improvement_s/se_s)` under the manifest's `critical_value_reference = normal_approx`, consuming the SAME quantized integers as the frozen margin test, so `none` here equals the shipped policy.
- **Selection layer.** A cohort the regime drops is forced `conservative = 0`, exactly like failing minimum sample; the fixed budget is then re-allocated across survivors with the frozen reward curve + `proportional_scale_to_budget`.
- **Ground truth.** Homogeneous per scenario from the simulator DGP: all cohorts TRUE-POSITIVE when `true_effect > 0`, all TRUE-NULL when `true_effect == 0`.
- **Power denominator.** The *payable* true-positive cohorts (candidate family `m`), not all cohorts. Control-arm cohorts are held out by design and contribute no data, so counting them would conflate test power with the assignment's treated fraction (~50%). Whole-cohort randomization here uses `between_cohort_vs_control_pool` identification, so only treated cohorts are ever payable.

## Results

| scenario | true_effect | label | regime | m | paid | waste (%B->null) | power (%payable-TP paid) | deployed (%B) | recovered (%B) |
|---|---|---|---|---|---|---|---|---|---|
| s1_strong_signal | 0.180 | true_positive | none | 19 | 7 | 0.00% | 36.84% | 73.75% | 26.25% |
| s1_strong_signal | 0.180 | true_positive | bonferroni | 19 | 2 | 0.00% | 10.53% | 37.85% | 62.15% |
| s1_strong_signal | 0.180 | true_positive | sidak | 19 | 2 | 0.00% | 10.53% | 37.85% | 62.15% |
| s1_strong_signal | 0.180 | true_positive | benjamini_hochberg | 19 | 6 | 0.00% | 31.58% | 69.22% | 30.78% |
| s2_null_effect | 0.000 | true_null | none | 17 | 2 | 29.61% | n/a | 29.61% | 70.39% |
| s2_null_effect | 0.000 | true_null | bonferroni | 17 | 1 | 25.94% | n/a | 25.94% | 74.06% |
| s2_null_effect | 0.000 | true_null | sidak | 17 | 1 | 25.94% | n/a | 25.94% | 74.06% |
| s2_null_effect | 0.000 | true_null | benjamini_hochberg | 17 | 1 | 25.94% | n/a | 25.94% | 74.06% |
| s3_low_power | 0.030 | true_positive | none | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |
| s3_low_power | 0.030 | true_positive | bonferroni | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |
| s3_low_power | 0.030 | true_positive | sidak | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |
| s3_low_power | 0.030 | true_positive | benjamini_hochberg | 4 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |
| s4_interference | 0.150 | true_positive | none | 22 | 8 | 0.00% | 36.36% | 100.00% | 0.00% |
| s4_interference | 0.150 | true_positive | bonferroni | 22 | 3 | 0.00% | 13.64% | 72.50% | 27.50% |
| s4_interference | 0.150 | true_positive | sidak | 22 | 3 | 0.00% | 13.64% | 72.50% | 27.50% |
| s4_interference | 0.150 | true_positive | benjamini_hochberg | 22 | 6 | 0.00% | 27.27% | 100.00% | 0.00% |
| s5_sybil_contamination | 0.150 | true_positive | none | 16 | 10 | 0.00% | 62.50% | 81.93% | 18.07% |
| s5_sybil_contamination | 0.150 | true_positive | bonferroni | 16 | 3 | 0.00% | 18.75% | 57.32% | 42.68% |
| s5_sybil_contamination | 0.150 | true_positive | sidak | 16 | 3 | 0.00% | 18.75% | 57.32% | 42.68% |
| s5_sybil_contamination | 0.150 | true_positive | benjamini_hochberg | 16 | 6 | 0.00% | 37.50% | 76.31% | 23.69% |
| s6_demand_shift | 0.050 | true_positive | none | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |
| s6_demand_shift | 0.050 | true_positive | bonferroni | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |
| s6_demand_shift | 0.050 | true_positive | sidak | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |
| s6_demand_shift | 0.050 | true_positive | benjamini_hochberg | 12 | 0 | 0.00% | 0.00% | 0.00% | 100.00% |

### Headline: `s2_null_effect` waste (budget paid under a TRUE ZERO effect)

| regime | cohorts paid | waste (share of budget) | budget recovered |
|---|---|---|---|
| none | 2 | 29.61% | 70.39% |
| bonferroni | 1 | 25.94% | 74.06% |
| sidak | 1 | 25.94% | 74.06% |
| benjamini_hochberg | 1 | 25.94% | 74.06% |

## Reading the scenarios

- **`s1_strong_signal` / `s5_sybil_contamination` (clear signal).** BH keeps materially more power than Bonferroni/Šidák while the true-null waste stays 0 (no null cohorts exist). This is the intended regime tradeoff.
- **`s2_null_effect` (the headline, true zero).** With no real signal, every paid cohort is waste. FWER and BH each cut the *count* of false positives from 2 to 1, but the one survivor still absorbs ~26% of the budget — the concentration residual (below).
- **`s3_low_power` (weak, true positive).** The design has essentially no per-cohort power; every regime (incl. `none`) pays nothing and recovers the whole budget. Correct, honest, and NOT something to tune away (CLAUDE.md invariant 8).
- **`s4_interference` (spillover-biased).** Spillover contaminates the between-cohort contrast, so the estimates are biased; the regimes still trade power for false-positive control the same way. Multiplicity control does not fix interference bias — that stays a sensitivity/guard-band problem, surfaced separately.
- **`s6_demand_shift` (confounding).** Its ratified design is `observational_replay` (pays zero regardless); run here in causal mode as a what-if, it *still* pays 0 under every regime — the conservative `between_cohort_vs_control_pool` SE carries the full between-cohort variance and already swamps the confounder, so no false positives even before any multiplicity correction. A clean demonstration that the conservative bound and the multiplicity layer are complementary guards, not substitutes.

## Structural note: a threshold correction mitigates, it does not remove, concentration

Under a true null (`s2`) the fixed budget does **not** shrink with the number of false positives —
it **concentrates**. `proportional_scale_to_budget` divides the *whole* budget across whichever
cohorts clear the test, so if two cohorts survive by chance they split the entire pool, not `2/60`
of it. This is a property of the reward *curve + overflow rule*, not of the p-value threshold, so
each regime addresses only part of the problem:

- **none.** No family-wise control. On `s2` a handful of chance winners absorb a large share of
  budget (the disclosed ~29.6% / 2-of-60 finding). Highest waste, highest concentration.
- **Bonferroni / Šidák (FWER).** Drive the per-cohort cut to ~`alpha/m` (≈0.0008 at m≈30–60).
  They **strongly reduce the count** of false positives — usually to zero under a pure null — so
  waste collapses toward 0. But they also crush power on the genuine-but-weak scenarios (`s3`, and
  the biased `s4`), turning "most cohorts get zero value" (our #1 risk-register item) into the
  default outcome. Bonferroni ⊂ Šidák (Šidák's cut is marginally larger, so weakly more power);
  under independence Šidák is exact, Bonferroni conservative.
- **Benjamini–Hochberg (FDR).** Controls the *expected proportion of paid cohorts that are false*,
  which is the closest statistical analogue to "proportion of spend wasted." It keeps far more
  power than FWER on `s1`/`s5` while still suppressing pure-null false discoveries, because its
  cut adapts to the number of true signals present. This is why it is the leading candidate.

**But note the residual, even under FDR — and this study measures it.** On `s2` (pure null) BH,
Bonferroni and Šidák all cut the false-positive *count* from 2 to 1, yet that single survivor
still absorbs **~26% of the budget** (vs ~30% under `none`). FDR bounds the *fraction of paid
cohorts* that are null; it does **not** bound the *fraction of budget* those few nulls receive,
because concentration is a spend-allocation effect. If even one null slips through on a scenario
with few true positives, the fixed-budget re-scaling hands it a disproportionate amount. So a
threshold regime alone cannot close the waste channel — the count drops far more than the spend.

**Flag for the architect (I do not decide this):** closing the residual needs a change to the
reward *curve / `value_scale`*, not only the p-value cut. Two candidate levers, both hash-moving
manifest changes and therefore v1.2-migration decisions:

1. a **floor on `conservative_effect`** below which no budget deploys (so marginal chance-winners
   with tiny effects earn nothing even if selected), and/or
2. a **concavity / per-cohort cap** in the reward curve so no single cohort can absorb a
   disproportionate share when few cohorts are paid (caps concentration directly).

A defensible package is **BH for the discovery threshold + a conservative-effect floor for the
concentration channel**, but selecting/parameterizing either is the architect's call against this
table, not the engine's. Any regime that adds a frozen field (an FDR level, a floor, a cap) moves
the manifest golden `74e0bb82…` and must be a deliberate v1.2 migration.
