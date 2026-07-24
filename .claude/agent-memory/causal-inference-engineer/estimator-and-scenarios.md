---
name: estimator-and-scenarios
description: Per-cohort estimators, identification modes, the six-scenario true-effect map, and per-scenario statistical-power findings
metadata:
  type: project
---

**Estimators (all simple/auditable — OLS, diff-in-means, sandwich; no causal ML).**
`estimators.py`. Cluster-robust CR1 (Cameron & Miller 2015 eq. 12), fixed effects ABSORBED via
within-demeaning (K counts only within-varying regressors, not LSDV dummies). Cluster = geo-cohort
for pooled; per-cohort effects have three identification modes: `within_cohort`,
`matched_stratum`, `between_cohort_vs_control_pool`.

**Simulator whole-cohort randomization → `between_cohort_vs_control_pool` identification.** Only
treated cohorts are ever payable; control cohorts are held out (contributed no data) and get
`identified=False`. The control-pool SE deliberately carries the FULL between-cohort variance
(`sqrt(s2_b*(1+1/G0))`) — conservative by design.

**Six benchmark scenarios (simulator/scenarios/*.json), true_effect map:**
- `s1_strong_signal`: true_effect=0.18, cluster_randomized → all TRUE-POSITIVE, clear signal.
- `s2_null_effect`: true_effect=0.0 → all TRUE-NULL (the false-positive headline scenario).
- `s3_low_power`: true_effect=0.03, n_cells=20, high noise → TRUE-POSITIVE but ~no power; engine
  correctly pays nothing / recovers whole budget under all regimes.
- `s4_interference`: true_effect=0.15, interference=0.6 → TRUE-POSITIVE but spillover biases the
  between-cohort contrast. Multiplicity control does NOT fix interference bias.
- `s5_sybil_contamination`: true_effect=0.15 → all TRUE-POSITIVE.
- `s6_demand_shift`: true_effect=0.05, confounding=0.5, native design `observational_replay`
  (pays zero regardless). Run in causal mode in the study it STILL pays 0 under every regime —
  the conservative control-pool SE already swamps the confounder. Clean demo that the conservative
  bound and multiplicity layer are complementary guards, not substitutes.

**Power findings (from multiplicity study, payable-family denominator):** s1 none 36.8% / BH 31.6%
/ FWER 10.5%; s5 none 62.5% / BH 37.5% / FWER 18.75%; s4 none 36.4% / BH 27.3% / FWER 13.6%.
BH consistently preserves materially more power than Bonferroni/Šidák. s3 & s6 = 0 power under all
regimes (honest — no recoverable signal).

**How to apply:** these are power *properties of the network/design*, not estimator defects. If a
scenario pays most cohorts zero, report it plainly (invariant 8). Related: [[multiplicity-study]].
