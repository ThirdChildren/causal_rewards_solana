---
name: absolute-allocation-ruling
description: RULING — reward allocation is ABSOLUTE (per-cohort curve output), not a share of budget; overflow_policy is downward-only; the 25.9% concentration is curve calibration, not normalization
metadata:
  type: project
---

**Ruling (2026-07-28, spec audit ordered by the project owner).** Allocation is **absolute**:
`alloc_c = reward_curve(conservative_c_s)`, a function of cohort `c` alone. `overflow_policy` applies
`min(1, B/S)` uniformly and only reduces; in the `S ≤ B` branch it is a **no-op**. Total is never
normalized up to `B`. Codified as **Property P-ABS**, `reward-policy.md` Appendix B.1 (non-normative
today; a hash-neutral normative promotion is proposal item C1).

**There is NO normalization bug.** `reward-policy.md` Stage 1 step 6, `manifest.schema.json`
`overflow_policy.description`, `protocol.md` invariant table, and
`causal-engine/src/crp_engine/reward_compiler.py` all agree. The wrong narrative lived ONLY in
non-normative prose: `reward-policy.md` Appendix A (fixed, erratum box), `multiplicity-recommendation.md`
(withdrawn), and the generated `docs/multiplicity-study.md` "Structural note" (source:
`causal-engine/src/crp_engine/studies.py` `_STRUCTURAL_NOTE` — causal-inference-engineer's fix).

**Why:** the s2_null_effect run deployed 29.61% / recovered 70.39%, i.e. `S ≤ B`, so the overflow rule
never executed. (s4_interference under `none` deploys 100.00% — that is the `S > B` branch existing.)

**The real defect is curve calibration.** The example curve pays ONE cohort 20% of `B` at its first
paying breakpoint and 120% of `B` at its last, with **no schema constraint** tying curve outputs to
`budget_base_units` or `cohort_count`. Under sparse payers the protocol has no concentration bound at
all — `proportional_scale_to_budget` only engages in the dense-payer case. Open as **Q-CURVE-1**.

**Two derived facts to re-check before using:** the s2 paid cohorts sit at `conservative_s ≈ 139600`
(25.94% of B) and `≈ 18350` (3.67%), inferred from published allocation percentages against the
example curve. If confirmed, a floor at `f_s = 50000` removes only the small one — the same cohort BH
already removes — so **floor(50000) and BH are redundant**, and BH+floor = either alone = 25.94%.

**How to apply:** never describe allocation as a share/split of the budget. Deployment fraction `S/B`
is an outcome, not a target. Concentration remedies must be argued on the CURVE side; multiplicity
thresholds provably cannot move concentration. Also: `overflow_policy`'s *name*
(`proportional_scale_to_budget`) reads as "normalize" and is the proximate cause of the misreading —
rename proposed as item C2.

Related: [[m3-spec-round-and-v1.2-proposal]], [[golden-hashes]].
