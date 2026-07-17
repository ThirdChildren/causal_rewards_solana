---
name: scenario-power-findings
description: Per-scenario statistical-power and interference findings from the M1 simulator alpha DGP; guides future estimator known-answer tests
metadata:
  type: project
---

Qualitative DGP behavior confirmed on the alpha-scale benchmark scenarios (2026-07-17,
`simulator/scenarios/`). These are the truths the M3 causal engine must RECOVER from observed
outcomes alone; use them to design known-answer tests. "naive gap" = raw control−treated mean
held_out_rmse (design-blind read); "true" = mean true per-cohort effect.

- **s1_strong_signal:** well-powered, true≈0.145, naive gap≈+0.102. Causal should win/tie.
- **s2_null_effect:** true=0.000, naive gap≈+0.013 (pure noise). Causal must pay ≈0; activity/
  quality still spend the whole budget → redundancy-waste story. Valid publishable NULL.
- **s3_low_power:** true=0.033 but high cluster noise + only 20 cells/8 blocks; only ~47/160
  (~29%) cohort-blocks meet the minimum-sample rule. Conservative bound ≤0 for most → causal pays
  little. HONEST low-power result, do NOT tune to manufacture payouts.
- **s4_interference (+s4b guardband):** interference=0.6 attenuates the naive effect (controls
  improve too). Guard band drops contaminated controls (alpha: 480/960 eligible) to recover a
  less-biased effect at sample cost. Always report bias + sensitivity range, never a bare point.
- **s5_sybil_contamination:** 35% Sybils, replication×3 inflates observations ~50k→90k with ZERO
  information value (Sybil obs get 0 info-weight in cohort quality aggregate). Activity/quality
  overpay; causal should not.
- **s6_demand_shift:** observational_replay with confounding=0.5 + seasonal demand FLIPS the naive
  gap sign (true≈+0.041, naive≈−0.032). Randomized S1 breaks the confound; observational replay is
  discovery-only, flag with unmeasured-confounding sensitivity bound.

**Top two risks to keep surfacing (concept note register):** (1) insufficient statistical power —
many networks can't clear a conservative lower bound; s2/s3 make this publishable. (2) interference
/ spillover — s4/s4b. Both can make causal LOSE to a simpler baseline in a realistic scenario;
per CLAUDE.md #8 that is an acceptable, reportable outcome.

Benchmark plan: `docs/benchmark-plan.md` (4 baselines activity/quality/scarcity/causal, one fixed
budget). See [[sim-determinism-and-serialization]].
