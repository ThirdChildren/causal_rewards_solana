# Benchmark Report — Causal Rewards Protocol (M4)

**Status:** SCAFFOLD (M4 deliverable). The results at target scale — 10,000 virtual sensors, 250
cohorts, 1,000,000 signed observations, four baselines under one fixed budget, across the six
scenarios — land in M4 after the v1.2 decision and the at-scale run (owner: `causal-inference-engineer`,
per `docs/m4-plan.md` tasks 9 and 12; the plan it executes is `docs/benchmark-plan.md`). This
scaffold fixes two things the final report MUST carry: the curve-provenance line and the limitations
section.

---

## Curve provenance (MANDATORY next to every published metric table)

The at-scale benchmark reads its reward curve from a **separate fixture**, not from the shipped spec
example (owner Condition 3; contract in `specs/v1.2-migration-proposal.md` "Benchmark manifest
fixture" and `docs/benchmark-plan.md` §7). Every metric table MUST be published with this line so a
reader sees exactly which curve produced the numbers:

> Curve source: `causal-engine/fixtures/benchmark-manifest.json` (recommended shipped-scale + 10%B
> saturating-cap default, `reward_curve_hash sha256:eeab732e…`); distinct from the spec example
> `specs/examples/manifest.example.json` (`reward_curve_hash sha256:14b0ec34…`). The spec example is
> unchanged; these numbers were produced by the recommended default (capped) curve, not the shipped
> example, and no recalibration was applied.

The fixture `reward_curve_hash` is FINALIZED (Condition 1, `docs/compensation-study.md`):
`sha256:eeab732ec6ff4cf09e1185b2b42ad5e5aa83524fefbd6f3d6b079ab43d227ff3` (shipped scale, per-cohort
ceiling = 10% of `B`; recalibration was evaluated and rejected on under-deployment grounds).

---

## Limitations

The honest boundaries below are first-class report content (owner ruling, 2026-07-30), not footnotes.

### No concentration bound and no waste bound

The protocol enforces the reward-curve **shape** deterministically — every party recomputes the
identical allocation from the frozen curve and the conservative per-cohort effects (Invariant 2). It
guarantees **neither a concentration bound** (a ceiling on how much of the budget one cohort can
absorb) **nor a waste bound** (a ceiling on budget flowing to cohorts that added no real value).
Under a true null the protocol correctly pays ~0 *in aggregate relative to budget* and recovers the
rest (Invariant 8), but a single chance cohort can still absorb a large share when the frozen curve
values one cohort highly — that is a **calibration property of the chosen curve, not a protocol
guarantee.** The chain **cannot certify targeting** (that spend reached genuinely additional cohorts)
without assuming the causal truth it is forbidden to assume (Invariant 6 — the chain verifies
process, not truth). Concentration is controllable only at the manifest level (a saturating
`reward_curve`, needing no new field); the recommended default — the shipped curve scale with a
per-cohort 10%`B` saturation cap (`specs/multiplicity-recommendation.md` §4; recalibration was
rejected on under-deployment grounds) — is guidance each experiment freezes for itself, not a
protocol-enforced constant. Where a scenario in this report shows concentration on few cohorts, that
reflects the frozen curve's calibration and the scenario's power, not a protocol defect.

### Null and low-power results are valid outputs

Per CLAUDE.md Invariant 8, scenarios where causal allocation pays little or nothing (the null and
low-power scenarios) are published as correct outcomes, not tuned away. This report does not adjust
the estimator to manufacture positive payouts.
