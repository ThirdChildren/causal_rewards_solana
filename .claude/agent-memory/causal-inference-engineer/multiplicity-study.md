---
name: multiplicity-study
description: Cross-cohort false-positive study — regime definitions, p-value choice, ground-truth labeling, and the budget-concentration finding that FDR does not remove
metadata:
  type: project
---

`crp_engine/multiplicity.py` + `crp_engine/studies.py` implement the §2.1 false-positive study
(regenerable artifact: `causal-rewards/docs/multiplicity-study.md`, via
`python -m crp_engine.studies`). Test: `tests/test_multiplicity.py`.

**Design choices (auditability over sophistication):**
- Four regimes as a SELECTION LAYER over per-cohort one-sided p-values: `none` (frozen default),
  `bonferroni` (`p<alpha/m`), `sidak` (`p<1-(1-alpha)^(1/m)`), `benjamini_hochberg` (FDR step-up).
  `alpha=0.05`, `m` = candidate family = eligible + identified + causal-design cohorts.
- p-value = `norm.sf(improvement_s/se_s)` under the manifest's `critical_value_reference =
  normal_approx`, consuming the SAME quantized integers as the frozen margin test, so `none`'s
  `p<0.05` reproduces the shipped `critical_value_micro=1_645_000` (`sf(1.645)=0.04998`).
- Selection feeds `reward_compiler.stage1_valuation(selected_cohorts=...)` (added as an OPTIONAL
  param, default `None` = frozen behavior byte-identical — a deselected cohort is forced
  conservative=0, exactly like failing min-sample). The `none` study cell uses the verbatim frozen
  compilation, not the p-value path, so it reports (not approximates) the default.
- Ground truth is homogeneous per scenario from the simulator DGP
  (`outcomes.py`: `cohort_effect = true_effect*(0.5+info)*het`, het>0): all TRUE-POSITIVE iff
  `true_effect>0`, all TRUE-NULL iff `true_effect==0`. Read straight off the scenario JSON.
- Power denominator = the PAYABLE true-positive family (candidates), NOT all cohorts — control-arm
  cohorts are design-held-out and can never be paid; counting them conflates test power with the
  ~50% treated fraction.

**Key finding (feeds architect, do NOT tune away — invariant 8):** on `s2_null_effect` (true zero)
`none` pays 2/60 cohorts = 29.6% of budget; Bonferroni/Šidák/BH each cut the *count* to 1 but that
survivor still absorbs ~26% of budget. Reason: the fixed budget under
`proportional_scale_to_budget` **concentrates** rather than shrinks — a spend-allocation effect a
p-value threshold cannot close. Flagged for architect: closing the residual needs a reward-curve /
`value_scale` change (a conservative-effect floor and/or a concavity/per-cohort cap), which are
hash-moving v1.2 manifest changes — the engine does NOT decide them. BH is the leading threshold
candidate (keeps power on s1/s5 while suppressing pure-null discoveries).

**How to apply:** do not change the frozen default (`none`) or add a frozen manifest field without
a deliberate v1.2 migration coordinated with protocol-architect. Related: [[estimator-and-scenarios]].
