# causal-engine/ — Causal engine (Python 3.11+)

Balance checks, estimators, uncertainty, sensitivity analysis, reward compiler.

## Rules

Typed. `numpy`/`scipy`/`pandas`. Cluster-robust SEs. Favor **simple auditable estimators**
over complex causal ML. All randomness seeded from the committed seed only. Pin everything;
ship a container digest. No wall-clock, no unseeded RNG, no locale/float nondeterminism.

## Invariants owned here

- **Conservative payouts** — `conservative_effect = max(0, effect - critical_value * standard_error)`.
  No positive payout from a cohort failing the min-sample rule or with bound ≤ 0.
- **Cohort-level estimand** — unit is geographic cohort within a time block, never a device.
- **Null results are valid outputs.**

**Status:** stub. Estimators/reward compiler land in M3; simulator alpha + benchmark plan in M1.

## License

MIT (analysis library).
